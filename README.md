# explain-benchmarks

Every number in my `$ explain` videos is measured on a real machine, not illustrated.
This repo holds the scripts behind them, so anyone can reproduce the results.

Each script needs only **Python** — nothing to install.

```bash
python3 uuid-primary-key/benchmark_uuid.py
```

## Benchmarks

| Topic | What it measures | Measured result |
|---|---|---|
| [Deadlock](deadlock/) | two transfers locking each other in opposite order | without lock ordering: **0/2** transfers complete, threads wait forever · with ordering: **2/2** in ~113 ms |
| [UUID primary key](uuid-primary-key/) | UUIDv4 vs UUIDv7 as a clustered primary key | 500,000 inserts: **3.68 s** vs **0.32 s** (11.51x) · pages rewritten per 10k inserts: **9,447** vs **298** (31.70x) · file size identical |
| [Vector search](vector-search/) | exact scan vs IVF clusters, speed **and** recall | nprobe=1: **58.8x** faster at **45.7%** recall · nprobe=16: **5.6x** faster at **98.7%** recall |
| [Safe retry](safe-retry/) | blind retry vs idempotency key + full jitter | 500 intents wrote **608 rows** (108 duplicates) vs **500** · retry peak **2,000** &rarr; **369** per 100 ms |
| [Load balancing](load-balancing/) | round robin vs least connections vs power of two | wait p99 **1,201 ms** &rarr; **290 ms** (4.1x), median **137 ms** &rarr; **5.5 ms** (25x) |
| [Index cost](index-cost/) | what an index gives and what it takes | reads **2,453x faster** · writes **+376%** (3 indexes +1,006%) · disk **+14%** · wide range **5.6x slower** |

## Reading the results

Every folder ships a `result.txt` — the raw output of the exact run used in the video.
Numbers may shift a little on your machine, but the conclusion will not.

---

Nguyen Viet Chung — AIDev
