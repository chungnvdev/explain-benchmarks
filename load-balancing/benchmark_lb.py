"""Load balancing: round robin is fair, and fair is not the same as fast.

Round robin hands request N to server N % k. That is perfectly even by COUNT. Real traffic is
not even by COST: most requests are cheap, a few are expensive. Round robin keeps posting new
work to a server that is still grinding through a heavy one, while its neighbours idle.

Three strategies over the exact same arrival stream and the exact same service times:

  round robin        next server in the rotation
  least connections  the server with the least outstanding work
  power of two       pick 2 servers at random, use the less loaded one

Discrete-event simulation, standard library only, fixed seed — the ranking reproduces exactly.

Run:  python3 benchmark_lb.py
"""

import random
import statistics

SERVERS = 4
REQUESTS = 20_000
ARRIVAL_GAP_MS = 6.5     # mean gap between arrivals (exponential) — keeps load near 80%
FAST_MS = 8.0            # the common, cheap request
SLOW_MS = 220.0          # the rare, expensive one
SLOW_SHARE = 0.06        # 6% of traffic is heavy
SEED = 20260820


def make_traffic(rng):
    """One arrival stream + one set of service times, shared by every strategy."""
    t, stream = 0.0, []
    for _ in range(REQUESTS):
        t += rng.expovariate(1.0 / ARRIVAL_GAP_MS)
        heavy = rng.random() < SLOW_SHARE
        service = SLOW_MS if heavy else FAST_MS
        stream.append((t, service, heavy))
    return stream


def simulate(stream, pick, rng):
    """free_at[s] = when server s finishes everything queued on it."""
    free_at = [0.0] * SERVERS
    waits, heavy_waits = [], []
    for i, (arrival, service, heavy) in enumerate(stream):
        s = pick(i, free_at, arrival, rng)
        start = max(arrival, free_at[s])
        wait = start - arrival
        free_at[s] = start + service
        waits.append(wait)
        if heavy:
            heavy_waits.append(wait)
    return waits, heavy_waits


def pct(values, p):
    return statistics.quantiles(values, n=1000, method="inclusive")[p - 1]


def main():
    import sys
    print(f"python {'.'.join(map(str, sys.version_info[:3]))} · standard library only")
    print(f"{SERVERS} servers · {REQUESTS:,} requests · mean gap {ARRIVAL_GAP_MS} ms")
    print(f"service time: {FAST_MS:.0f} ms for {100 - SLOW_SHARE * 100:.0f}% of requests, "
          f"{SLOW_MS:.0f} ms for {SLOW_SHARE * 100:.0f}%")
    print("same arrival stream and same service times for every strategy\n")

    rng = random.Random(SEED)
    stream = make_traffic(rng)
    load = sum(s for _, s, _ in stream) / (stream[-1][0] * SERVERS)
    print(f"offered load: {load * 100:.1f}% of total capacity\n")

    strategies = [
        ("round robin", lambda i, free, now, r: i % SERVERS),
        ("least connections", lambda i, free, now, r: min(range(SERVERS), key=lambda s: free[s])),
        ("power of two", lambda i, free, now, r: (lambda a, b: a if free[a] <= free[b] else b)(
            r.randrange(SERVERS), r.randrange(SERVERS))),
    ]

    rows = []
    for name, pick in strategies:
        waits, heavy = simulate(stream, pick, random.Random(SEED + 1))
        rows.append({
            "name": name,
            "p50": pct(waits, 500),
            "p95": pct(waits, 950),
            "p99": pct(waits, 990),
            "max": max(waits),
            "mean": statistics.fmean(waits),
        })
        r = rows[-1]
        print(f"{name:<20} p50 {r['p50']:7.1f} ms · p95 {r['p95']:8.1f} ms · "
              f"p99 {r['p99']:8.1f} ms · worst {r['max']:8.1f} ms")

    rr = rows[0]
    print("\nRESULT  (queue wait, milliseconds)")
    print(f"{'strategy':<20}{'p50':>9}{'p95':>10}{'p99':>10}{'worst':>10}{'p99 vs RR':>12}")
    for r in rows:
        ratio = rr["p99"] / r["p99"] if r["p99"] else 0
        tag = "—" if r is rr else f"{ratio:.1f}x better"
        print(f"{r['name']:<20}{r['p50']:>9.1f}{r['p95']:>10.1f}{r['p99']:>10.1f}"
              f"{r['max']:>10.1f}{tag:>12}")

    best = min(rows[1:], key=lambda r: r["p99"])
    print(f"\nSame servers, same traffic, one line of config: p99 wait "
          f"{rr['p99']:.0f} ms -> {best['p99']:.0f} ms ({rr['p99'] / best['p99']:.1f}x better).")


if __name__ == "__main__":
    main()
