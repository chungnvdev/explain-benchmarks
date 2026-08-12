# Deadlock

Two transfers run at the same time: account 1 → 2, and account 2 → 1.
Each one locks its source account, does a little work, then locks the destination.

Thread A ends up holding lock 1 while waiting for lock 2.
Thread B holds lock 2 while waiting for lock 1. Neither can move.
Nothing crashes, nothing is logged — the system simply stops.

## Run it

```bash
python3 benchmark_deadlock.py
```

## Measured results

| | Without lock ordering | With lock ordering |
|---|---|---|
| Transfers completed | **0/2** — all 5 runs | **2/2** — all 5 runs |
| Time | stuck until the script gives up | **~113 ms** |

The fix is **lock ordering**: every thread acquires locks in the same global order
(here, ascending account id) no matter which direction the money flows.

Raw output: [result.txt](result.txt)
