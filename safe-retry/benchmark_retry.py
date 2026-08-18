"""Retrying is not free: what a naive retry does to your data, and to your server.

Two things go wrong when a client retries the obvious way.

Part A — the response was lost, not the work. The server already wrote the row; only the
reply died on the way back. A client that retries a non-idempotent write duplicates real
records. The same run with a UNIQUE idempotency key writes each intent exactly once.

Part B — everyone retries on the same clock. Clients that failed together retry together, so
the struggling server gets a spike instead of a trickle. Exponential backoff with full jitter
spreads the same number of retries over time.

Standard library only (sqlite3, random) — nothing to install. Deterministic seed, so the
numbers reproduce exactly.

Run:  python3 benchmark_retry.py
"""

import random
import sqlite3
import time

REQUESTS = 500          # part A: distinct payment intents
LOST_REPLY_RATE = 0.18  # share of calls where the write lands but the reply is lost
MAX_ATTEMPTS = 4        # 1 initial call + 3 retries

CLIENTS = 2_000         # part B: clients that all fail at t=0
RETRIES = 3
BASE_DELAY = 1.0        # seconds
WINDOW = 0.1            # bucket width used to measure the peak, in seconds
SEED = 20260819


def part_a():
    """Same traffic, same failures — with and without an idempotency key."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE naive (id INTEGER PRIMARY KEY, intent TEXT, amount INTEGER)")
    con.execute(
        "CREATE TABLE keyed (id INTEGER PRIMARY KEY, intent TEXT, amount INTEGER,"
        " idem_key TEXT UNIQUE)"
    )

    rng = random.Random(SEED)
    calls = 0
    for i in range(REQUESTS):
        intent = f"order-{i}"
        key = f"key-{i}"                      # client generates it once, reuses on retry
        attempts = 1
        while attempts <= MAX_ATTEMPTS:
            calls += 1
            # The server always performs the write; sometimes the reply never arrives.
            con.execute("INSERT INTO naive (intent, amount) VALUES (?, ?)", (intent, 50))
            try:
                con.execute(
                    "INSERT INTO keyed (intent, amount, idem_key) VALUES (?, ?, ?)",
                    (intent, 50, key),
                )
            except sqlite3.IntegrityError:
                pass                          # same key -> already applied, nothing to do
            if rng.random() >= LOST_REPLY_RATE:
                break                         # client got the reply, stops retrying
            attempts += 1
    con.commit()

    naive_rows = con.execute("SELECT COUNT(*) FROM naive").fetchone()[0]
    keyed_rows = con.execute("SELECT COUNT(*) FROM keyed").fetchone()[0]
    naive_amount = con.execute("SELECT COALESCE(SUM(amount), 0) FROM naive").fetchone()[0]
    keyed_amount = con.execute("SELECT COALESCE(SUM(amount), 0) FROM keyed").fetchone()[0]
    con.close()
    return {
        "intents": REQUESTS,
        "calls": calls,
        "naive_rows": naive_rows,
        "keyed_rows": keyed_rows,
        "naive_amount": naive_amount,
        "keyed_amount": keyed_amount,
    }


def histogram(schedule):
    """Arrivals per WINDOW-wide bucket, indexed by bucket number."""
    buckets = {}
    for t in schedule:
        b = int(t / WINDOW)
        buckets[b] = buckets.get(b, 0) + 1
    return buckets


def peak(schedule):
    """Highest number of arrivals landing inside one WINDOW-wide bucket."""
    buckets = histogram(schedule)
    return max(buckets.values()), len(buckets)


def part_b():
    """Fixed-interval retries vs exponential backoff with full jitter."""
    rng = random.Random(SEED)
    fixed, jittered = [], []
    for _ in range(CLIENTS):
        for n in range(RETRIES):
            fixed.append(BASE_DELAY * (n + 1))                       # 1s, 2s, 3s — same for all
            jittered.append(rng.uniform(0, BASE_DELAY * (2 ** n)))   # full jitter, AWS style
    f_peak, f_buckets = peak(fixed)
    j_peak, j_buckets = peak(jittered)
    return {
        "fixed_hist": histogram(fixed),
        "jitter_hist": histogram(jittered),
        "retries_total": CLIENTS * RETRIES,
        "fixed_peak": f_peak,
        "fixed_buckets": f_buckets,
        "jitter_peak": j_peak,
        "jitter_buckets": j_buckets,
        "spread": f_peak / j_peak,
    }


def main():
    import sys
    print(f"python {'.'.join(map(str, sys.version_info[:3]))} · sqlite3 {sqlite3.sqlite_version}")
    print(f"seed {SEED} · standard library only, nothing installed\n")

    print(f"PART A — {REQUESTS} payment intents, {int(LOST_REPLY_RATE * 100)}% of replies lost, "
          f"up to {MAX_ATTEMPTS - 1} retries")
    a = part_a()
    print(f"  calls that reached the server : {a['calls']:,}")
    print(f"  rows written, no idem key     : {a['naive_rows']:,}  "
          f"(charged ${a['naive_amount']:,})")
    print(f"  rows written, UNIQUE idem key : {a['keyed_rows']:,}  "
          f"(charged ${a['keyed_amount']:,})")
    dup = a["naive_rows"] - a["intents"]
    print(f"  duplicate records             : {dup:,}  "
          f"({dup / a['intents'] * 100:.1f}% of intents charged more than once)")
    print(f"  money charged in excess       : ${a['naive_amount'] - a['keyed_amount']:,}\n")

    print(f"PART B — {CLIENTS:,} clients fail at the same instant, {RETRIES} retries each")
    b = part_b()
    print(f"  retries scheduled             : {b['retries_total']:,}")
    print(f"  fixed 1s/2s/3s → peak         : {b['fixed_peak']:,} requests in one "
          f"{int(WINDOW * 1000)} ms window ({b['fixed_buckets']} windows used)")
    print(f"  full jitter    → peak         : {b['jitter_peak']:,} requests in one "
          f"{int(WINDOW * 1000)} ms window ({b['jitter_buckets']} windows used)")
    print(f"  peak reduced by               : {b['spread']:.1f}x\n")

    slots = 40  # 40 x 100 ms = the first 4 seconds, the window the video draws
    fx = [b["fixed_hist"].get(i, 0) for i in range(slots)]
    jt = [b["jitter_hist"].get(i, 0) for i in range(slots)]
    print(f"  arrivals per 100 ms bucket, first {slots} buckets")
    print(f"    fixed  : {fx}")
    print(f"    jitter : {jt}\n")

    print("RESULT")
    print(f"{'metric':<34}{'naive retry':>14}{'safe retry':>14}")
    print(f"{'records written (500 intents)':<34}{a['naive_rows']:>14,}{a['keyed_rows']:>14,}")
    print(f"{'money charged':<34}{'$' + format(a['naive_amount'], ','):>14}"
          f"{'$' + format(a['keyed_amount'], ','):>14}")
    print(f"{'peak load in a 100 ms window':<34}{b['fixed_peak']:>14,}{b['jitter_peak']:>14,}")


if __name__ == "__main__":
    main()
