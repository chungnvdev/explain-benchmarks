# Streaming does not make the answer faster

It moves *when* the first byte arrives, not *how long* the whole thing takes. This measures both
on one local HTTP server: a 300-token answer served buffered (one `Content-Length` response) and
streamed (`Transfer-Encoding: chunked`, one chunk per token).

Nothing sleeps. Producing each token costs real CPU work (repeated SHA-256), so every duration
here is wall-clock time the machine actually spent.

## Run it

```bash
python3 benchmark_streaming_ttfb.py
```

Python 3 standard library only (`http.server` + `socket`), fixed seed, 7 interleaved A/B rounds.

## Measured results

| | Buffered | Streaming |
|---|---|---|
| Time to first byte | 4,462.7 ms | **6.5 ms** — 687x sooner |
| Time to last byte | 4.043 s (best of 7) | 4.063 s — **+0.5%, unchanged** |
| Bytes on the wire | 2,255 B | **3,766 B (+67%)** for the same text |
| Readable after 2.0 s | 0 / 300 tokens | **144 / 300 (48%)** |
| Reader closes the tab at 2.0 s | 0 bytes received | 1,877 B = 143 tokens |
| Server work burned on that reader | **300/300 tokens, 4.17 s** | 144/300, 2.01 s |

The +67% is chunked framing: every 7-byte token carries a hex size line and two CRLFs of its own.

The last row is the part nobody shows. `/buffered` does not touch the socket until the final
token exists, so a reader who walks away at second 2 still costs the full 4.17 s of generation.
`/stream` writes each token as it appears and finds out on the very next `write()`.

**A trap worth knowing.** The first version of the abandonment test had the client "close the tab"
at 2.0 s while still blocked inside `recv()` — it happily received the whole buffered response at
4.4 s. The socket timeout has to be set to the remaining time before the deadline
(`settimeout(deadline - elapsed)`) for the measurement to model a reader who actually left.

Raw output: [result.txt](result.txt)
