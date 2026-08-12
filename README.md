# explain-benchmarks

Every number in my `$ explain` videos is measured on a real machine, not illustrated.
This repo holds the scripts behind them, so anyone can reproduce the results.

Each script needs only **Python** — nothing to install.

```bash
python3 deadlock/benchmark_deadlock.py
```

## Benchmarks

| Topic | What it measures | Measured result |
|---|---|---|
| [Deadlock](deadlock/) | two transfers locking each other in opposite order | without lock ordering: **0/2** transfers complete, threads wait forever · with ordering: **2/2** in ~113 ms |

## Reading the results

Every folder ships a `result.txt` — the raw output of the exact run used in the video.
Numbers may shift a little on your machine, but the conclusion will not.

---

Nguyen Viet Chung — AIDev
