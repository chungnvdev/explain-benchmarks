# UUIDv4 vs UUIDv7 as a primary key

A table whose primary key is the clustered index stores rows physically in key order.

`UUIDv4` is 122 random bits, so every new row lands on a random page in the middle of the
B-tree, and each commit has to rewrite every page it touched. `UUIDv7` puts a 48-bit
millisecond timestamp first (RFC 9562 §5.7), so new rows always append to the tail page.

The benchmark inserts 500,000 rows into a SQLite `WITHOUT ROWID` table — SQLite's clustered
primary key, the same layout InnoDB uses — once with v4 keys and once with v7 keys.

It then measures **write amplification** directly: switch to WAL mode, checkpoint, insert one
more batch of 10,000 rows, and read the `-wal` file size. Every modified page is one WAL frame,
so the file size tells you exactly how many 4 KB pages that batch rewrote.

The whole pair runs twice with the insert order flipped, so a warm page cache cannot explain
the gap. The reported table takes UUIDv4's fastest run against UUIDv7's slowest one.

## Run it

```bash
python3 benchmark_uuid.py
```

Needs Python 3.14+ (`uuid.uuid7()` landed in the standard library there). Nothing to install.

## Measured results

| Metric | UUIDv4 | UUIDv7 | Ratio |
|---|---|---|---|
| Insert 500,000 rows | 3.68 s | **0.32 s** | **11.51x faster** |
| Insert rate | 135,796 rows/s | **1,562,597 rows/s** | 11.51x |
| Pages rewritten by the next 10,000 inserts | 9,447 | **298** | **31.70x fewer** |
| Database file | 57.68 MB | 56.98 MB | 1.01x — same |
| Pages in file (4 KB) | 14,453 | 14,299 | 1.01x — same |
| Point lookup by key | 0.00 ms | 0.00 ms | 0.99x — same |

The popular claim is that random keys bloat the index. Measured, they do not: the file is the
same size and reads are just as fast. The cost is writes — the engine rewrites 31x more pages
for the same number of rows.

The trade-off of v7: the creation time sits in the ID, so anyone holding an ID knows when the
row was written and can estimate how fast rows are produced.

Raw output: [result.txt](result.txt)
