# What an index gives you, and what it takes back

Everybody measures the good half. This measures the whole bill on one real SQLite database of
300,000 rows: reads, writes, disk, and the case where the index actively loses.

## Run it

```bash
python3 benchmark_index_cost.py
```

Python 3 standard library only (sqlite3), fixed seed.

## Measured results

| | Without index | With index |
|---|---|---|
| Point lookup `WHERE user_id = ?` | 11.691 ms | **0.005 ms** — 2,453x faster |
| Insert 100,000 rows | 0.06 s | **0.27 s** (+376%) · three indexes **0.64 s** (+1,006%) |
| Database file | 23.50 MB | **26.74 MB** (+14%, one index costs 3.24 MB) |
| Range matching 30% of rows | **14.73 ms** (scan) | **81.99 ms** (forced index) — 5.6x slower |

On that last query SQLite picks `SCAN events` on its own: walking the index and jumping back
into the table 89,126 times costs more than reading the table straight through.

**A trap worth knowing.** The first version of that measurement used `COUNT(*)`, which SQLite
answers from a *covering index* (`USING COVERING INDEX`) without touching the table at all —
the index appeared to win. The query has to read a column the index does not carry (`payload`)
before the cost of returning to the table shows up.

Raw output: [result.txt](result.txt)
