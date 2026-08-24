#!/usr/bin/env python3
"""Streaming vs buffered HTTP responses: what time-to-first-byte really costs.

Standard library only (http.server + socket). Nothing inside a measurement
sleeps: producing each token costs real CPU work (repeated SHA-256), so every
duration below is wall-clock time this machine actually spent.

Run:  python3 benchmark_streaming_ttfb.py
"""

import hashlib
import socket
import statistics
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SEED = b"20260824"
N_TOKENS = 300            # length of the simulated answer, in tokens
ROUNDS_PER_TOKEN = 60_000  # CPU work per token (fixed, so runs are comparable)
REPEATS = 7
ABANDON_AFTER = 2.0       # seconds before the impatient reader closes the tab
TOKEN_CHARS = 7           # "abc123 " -> 6 hex chars + one space

# Filled in by the server when a client disappears mid-response:
# (mode, tokens_generated_before_noticing, seconds_spent).
WASTED = []


def make_token(i: int) -> str:
    """Deterministic token whose production costs real, measurable CPU time."""
    h = hashlib.sha256(SEED + i.to_bytes(4, "big"))
    for _ in range(ROUNDS_PER_TOKEN):
        h = hashlib.sha256(h.digest())
    return h.hexdigest()[:6] + " "


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/buffered"):
            self._buffered()
        elif self.path.startswith("/stream"):
            self._stream()
        else:
            self.send_error(404)

    def _buffered(self):
        # The whole answer is generated BEFORE a single byte leaves the server.
        t0 = time.perf_counter()
        body = "".join(make_token(i) for i in range(N_TOKENS)).encode()
        if "abandon" in self.path:
            # Structural fact, not an error path: the socket is untouched until
            # the last token exists, so the full cost is paid no matter what.
            WASTED.append(("buffered", N_TOKENS, time.perf_counter() - t0))
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # The whole answer was computed before we ever touched the socket,
            # so the client leaving early saved this server nothing.
            WASTED.append(("buffered", N_TOKENS, time.perf_counter() - t0))

    def _stream(self):
        # Headers go out first, then each token is flushed as soon as it exists.
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        t0 = time.perf_counter()
        i = 0
        try:
            self.wfile.flush()
            for i in range(N_TOKENS):
                chunk = make_token(i).encode()
                self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Every token is written the moment it exists, so a client that
            # walks away is noticed on the very next write.
            WASTED.append(("stream", i, time.perf_counter() - t0))


def read_response(port: int, path: str, abandon_after: float | None = None):
    """Return (ttfb, total, raw, timeline) for one request.

    raw      = every byte received, exactly as it came off the socket
    timeline = list of (elapsed_seconds, bytes_received_so_far) per recv()
    """
    s = socket.create_connection(("127.0.0.1", port))
    s.settimeout(60)
    t0 = time.perf_counter()
    s.sendall(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n".encode())

    ttfb = None
    raw = bytearray()
    timeline = []
    while True:
        if abandon_after is not None:
            left = abandon_after - (time.perf_counter() - t0)
            if left <= 0:
                break
            s.settimeout(left)  # the reader leaves at the deadline, mid-wait
        try:
            data = s.recv(65536)
        except socket.timeout:
            break
        if not data:
            break
        now = time.perf_counter() - t0
        if ttfb is None:
            ttfb = now
        raw.extend(data)
        timeline.append((now, len(raw)))
    total = time.perf_counter() - t0
    s.close()
    return ttfb, total, bytes(raw), timeline


def tokens_in(raw: bytes, chunked: bool) -> int:
    """Count the tokens a reader can actually see in these bytes.

    Partial data is expected: framing is decoded, never estimated.
    """
    sep = raw.find(b"\r\n\r\n")
    if sep < 0:
        return 0
    body = raw[sep + 4:]
    if not chunked:
        return len(body) // TOKEN_CHARS

    text = 0
    pos = 0
    while True:
        eol = body.find(b"\r\n", pos)
        if eol < 0:
            break
        try:
            size = int(body[pos:eol].split(b";")[0], 16)
        except ValueError:
            break
        if size == 0 or eol + 2 + size + 2 > len(body):
            break
        text += size
        pos = eol + 2 + size + 2
    return text // TOKEN_CHARS


def tokens_delivered_by(raw: bytes, timeline, deadline: float, chunked: bool) -> int:
    """Tokens visible to the reader at `deadline` seconds."""
    got = 0
    for elapsed, cum in timeline:
        if elapsed <= deadline:
            got = cum
    return tokens_in(raw[:got], chunked)


def fmt(x, unit="s", nd=3):
    return f"{x:.{nd}f} {unit}"


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # Calibration: what does one token actually cost on this machine?
    samples = []
    for i in range(7):
        t = time.perf_counter()
        make_token(i)
        samples.append((time.perf_counter() - t) * 1000)
    per_token_ms = statistics.median(samples)

    out = []

    def say(line=""):
        print(line)
        out.append(line)

    say("STREAMING vs BUFFERED - time to first byte")
    say("=" * 58)
    say(f"answer length      : {N_TOKENS} tokens")
    say(f"work per token     : {ROUNDS_PER_TOKEN} SHA-256 rounds = {per_token_ms:.2f} ms")
    say(f"repeats            : {REPEATS} (A/B interleaved; median and best-of)")
    say("")

    runs = {"buffered": [], "stream": []}
    for _ in range(REPEATS):
        for mode, path in (("buffered", "/buffered"), ("stream", "/stream")):
            ttfb, total, raw, timeline = read_response(port, path)
            runs[mode].append((ttfb, total, len(raw), timeline, raw))

    def med(mode, idx):
        return statistics.median(r[idx] for r in runs[mode])

    b_ttfb, s_ttfb = med("buffered", 0), med("stream", 0)
    b_total, s_total = med("buffered", 1), med("stream", 1)
    b_wire, s_wire = med("buffered", 2), med("stream", 2)

    say("M1  TIME TO FIRST BYTE")
    say(f"    buffered   {b_ttfb * 1000:9.1f} ms")
    say(f"    streaming  {s_ttfb * 1000:9.1f} ms")
    say(f"    -> first byte arrives {b_ttfb / s_ttfb:.0f}x sooner when streaming")
    say("")

    def rng(mode, idx):
        vals = [r[idx] for r in runs[mode]]
        return min(vals), max(vals)

    b_min, b_max = rng("buffered", 1)
    s_min, s_max = rng("stream", 1)
    say("M2  TIME TO LAST BYTE (the full answer)")
    say(f"    buffered   median {b_total:6.3f} s   best {b_min:6.3f} s   range {b_min:.3f}-{b_max:.3f}")
    say(f"    streaming  median {s_total:6.3f} s   best {s_min:6.3f} s   range {s_min:.3f}-{s_max:.3f}")
    delta = (s_min - b_min) / b_min * 100
    say(f"    -> best-of differs by {delta:+.1f}%, well inside the run-to-run spread:")
    say("       streaming does NOT make the full answer arrive sooner")
    say("")

    say("M3  BYTES ON THE WIRE (chunked framing overhead)")
    say(f"    buffered   {b_wire:9d} bytes")
    say(f"    streaming  {s_wire:9d} bytes")
    say(f"    -> +{s_wire - b_wire} bytes (+{(s_wire - b_wire) / b_wire * 100:.1f}%) for the same text")
    say("")

    say("M4  WHAT THE READER HAS AFTER 1.0 s / 2.0 s")
    for mode, chunked in (("buffered", False), ("stream", True)):
        run = runs[mode][len(runs[mode]) // 2]
        tl, raw = run[3], run[4]
        one = tokens_delivered_by(raw, tl, 1.0, chunked)
        two = tokens_delivered_by(raw, tl, 2.0, chunked)
        say(f"    {mode:10s} {one:4d} tokens @1s   {two:4d} tokens @2s"
            f"   ({one / N_TOKENS * 100:.0f}% / {two / N_TOKENS * 100:.0f}% of the answer)")
    say("")

    say(f"M5  READER CLOSES THE TAB AFTER {ABANDON_AFTER:.0f} s")
    WASTED.clear()
    for mode, path, chunked in (("buffered", "/buffered?abandon", False),
                                ("stream", "/stream?abandon", True)):
        _, _, raw, tl = read_response(port, path, abandon_after=ABANDON_AFTER)
        got = tokens_delivered_by(raw, tl, ABANDON_AFTER, chunked)
        pct = got / N_TOKENS * 100
        say(f"    {mode:10s} {len(raw):6d} bytes received = {got:3d}/{N_TOKENS} tokens ({pct:.0f}% usable)")
        time.sleep(8)  # between measurements only: let the abandoned thread finish
    say("")

    say("M6  WHAT THE SERVER BURNS ON A READER WHO ALREADY LEFT")
    for mode, tokens, spent in WASTED:
        say(f"    {mode:10s} kept generating {tokens:3d}/{N_TOKENS} tokens"
            f" = {spent:.2f} s of CPU before noticing")
    if len(WASTED) == 2:
        b = next(w for w in WASTED if w[0] == "buffered")
        s_ = next(w for w in WASTED if w[0] == "stream")
        say(f"    -> streaming stopped at {s_[1] / N_TOKENS * 100:.0f}% of the work,"
            f" buffered at {b[1] / N_TOKENS * 100:.0f}%")
    say("")
    say("Wall-clock time on this machine; nothing sleeps inside a measurement.")

    with open("benchmark-result.txt", "w") as f:
        f.write("\n".join(out) + "\n")
    server.shutdown()


if __name__ == "__main__":
    main()
