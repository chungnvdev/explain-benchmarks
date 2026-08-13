"""Random vs time-ordered primary keys: UUIDv4 vs UUIDv7 on a clustered B-tree.

Both tables are declared WITHOUT ROWID, so the primary key IS the table's
B-tree (the same layout MySQL/InnoDB uses for a clustered primary key).
Random keys land on random pages, so the engine keeps splitting pages it
already wrote; time-ordered keys always append to the right-most page.

Nothing to install: standard library only (Python 3.14+ for uuid.uuid7).
Run:  python3 benchmark_uuid.py
"""

import os
import random
import sqlite3
import tempfile
import time
import uuid

ROWS = 500_000
BATCH = 10_000
PAYLOAD = "x" * 80  # keep every row the same size for both runs
LOOKUPS = 2_000
SEED = 20260815


def touched_pages(con: sqlite3.Connection, keys: list[bytes]) -> int:
    """How many 4 KB pages one batch of inserts actually rewrites.

    In WAL mode every modified page is appended to the -wal file as one frame
    (24-byte header + page). Checkpoint + truncate first, insert one batch,
    then read the frame count straight off the WAL file size.
    """
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    wal_path = con.execute("PRAGMA database_list").fetchall()[0][2] + "-wal"
    page_size = con.execute("PRAGMA page_size").fetchone()[0]

    con.executemany(
        "INSERT INTO events (id, payload) VALUES (?, ?)", ((k, PAYLOAD) for k in keys)
    )
    con.commit()
    wal_bytes = os.path.getsize(wal_path)
    return max(0, (wal_bytes - 32) // (page_size + 24))  # 32-byte WAL header


def build(db_path: str, keys: list[bytes], extra_keys: list[bytes]) -> dict:
    """Insert keys into a clustered-B-tree table and measure time + size."""
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE events (id BLOB PRIMARY KEY, payload TEXT) WITHOUT ROWID")
    con.commit()

    start = time.perf_counter()
    for i in range(0, ROWS, BATCH):
        con.executemany(
            "INSERT INTO events (id, payload) VALUES (?, ?)",
            ((k, PAYLOAD) for k in keys[i : i + BATCH]),
        )
        con.commit()
    insert_s = time.perf_counter() - start

    page_size = con.execute("PRAGMA page_size").fetchone()[0]
    page_count = con.execute("PRAGMA page_count").fetchone()[0]

    rng = random.Random(SEED)
    probes = [rng.choice(keys) for _ in range(LOOKUPS)]
    start = time.perf_counter()
    for k in probes:
        con.execute("SELECT payload FROM events WHERE id = ?", (k,)).fetchone()
    lookup_ms = (time.perf_counter() - start) * 1000 / LOOKUPS

    # "100 newest rows": v7 keys are time-ordered so the key itself answers it.
    start = time.perf_counter()
    con.execute("SELECT id FROM events ORDER BY id DESC LIMIT 100").fetchall()
    newest_ms = (time.perf_counter() - start) * 1000

    pages_touched = touched_pages(con, extra_keys)

    con.close()
    return {
        "insert_s": insert_s,
        "rows_per_s": ROWS / insert_s,
        "file_bytes": os.path.getsize(db_path),
        "page_size": page_size,
        "page_count": page_count,
        "bytes_per_row": os.path.getsize(db_path) / ROWS,
        "lookup_ms": lookup_ms,
        "newest_ms": newest_ms,
        "pages_touched": pages_touched,
    }


def main() -> None:
    print(f"Python {'.'.join(map(str, __import__('sys').version_info[:3]))} · sqlite3 {sqlite3.sqlite_version}")
    print(f"{ROWS:,} rows · payload {len(PAYLOAD)} bytes · WITHOUT ROWID (clustered primary key)")
    print(f"batch commit every {BATCH:,} rows · SQLite defaults (journal=delete, synchronous=FULL)\n")

    rng = random.Random(SEED)
    v4_keys = [uuid.UUID(int=rng.getrandbits(128), version=4).bytes for _ in range(ROWS)]
    v4_extra = [uuid.UUID(int=rng.getrandbits(128), version=4).bytes for _ in range(BATCH)]
    v7_keys = [uuid.uuid7().bytes for _ in range(ROWS)]
    v7_extra = [uuid.uuid7().bytes for _ in range(BATCH)]

    print(f"sample v4  {v4_keys[0].hex()}  ->  {v4_keys[-1].hex()}   (no order)")
    print(f"sample v7  {v7_keys[0].hex()}  ->  {v7_keys[-1].hex()}   (ascending)\n")
    print(f"v7 keys sorted ascending: {v7_keys == sorted(v7_keys)}")
    print(f"v4 keys sorted ascending: {v4_keys == sorted(v4_keys)}\n")

    # Run the pair twice with the order flipped, so nobody can blame warm cache.
    runs = []
    with tempfile.TemporaryDirectory() as tmp:
        for pass_no, order in enumerate((("UUIDv4", "UUIDv7"), ("UUIDv7", "UUIDv4")), start=1):
            keyset = {"UUIDv4": (v4_keys, v4_extra), "UUIDv7": (v7_keys, v7_extra)}
            result = {}
            print(f"pass {pass_no} — order: {order[0]} then {order[1]}")
            for name in order:
                keys, extra = keyset[name]
                path = os.path.join(tmp, f"{name}-p{pass_no}.db")
                print(f"  inserting {ROWS:,} rows with {name} primary key ...", flush=True)
                result[name] = build(path, keys, extra)
                r = result[name]
                print(
                    f"    {r['insert_s']:.2f} s  ·  {r['rows_per_s']:,.0f} rows/s  ·  "
                    f"{r['file_bytes'] / 1048576:.1f} MB  ·  {r['page_count']:,} pages  ·  "
                    f"{r['pages_touched']:,} pages rewritten by the next {BATCH:,} inserts",
                    flush=True,
                )
                os.remove(path)
            runs.append(result)
            print()

    # Report the slower (worst-case for v7) of the two passes: the conservative read.
    v4 = min((r["UUIDv4"] for r in runs), key=lambda r: r["insert_s"])
    v7 = max((r["UUIDv7"] for r in runs), key=lambda r: r["insert_s"])
    print("Reporting the pass that flatters UUIDv4 most (its fastest run vs UUIDv7's slowest).\n")
    print("RESULT")
    print(f"{'metric':<26}{'UUIDv4':>14}{'UUIDv7':>14}{'ratio':>12}")
    rows = [
        ("insert time (s)", v4["insert_s"], v7["insert_s"], v4["insert_s"] / v7["insert_s"]),
        ("insert rate (rows/s)", v4["rows_per_s"], v7["rows_per_s"], v7["rows_per_s"] / v4["rows_per_s"]),
        ("db file (MB)", v4["file_bytes"] / 1048576, v7["file_bytes"] / 1048576, v4["file_bytes"] / v7["file_bytes"]),
        ("pages (4 KB)", v4["page_count"], v7["page_count"], v4["page_count"] / v7["page_count"]),
        ("bytes per row", v4["bytes_per_row"], v7["bytes_per_row"], v4["bytes_per_row"] / v7["bytes_per_row"]),
        ("point lookup (ms)", v4["lookup_ms"], v7["lookup_ms"], v4["lookup_ms"] / v7["lookup_ms"]),
        ("100 newest rows (ms)", v4["newest_ms"], v7["newest_ms"], v4["newest_ms"] / v7["newest_ms"]),
        (f"pages rewritten / {BATCH // 1000}k ins", v4["pages_touched"], v7["pages_touched"],
         v4["pages_touched"] / max(1, v7["pages_touched"])),
    ]
    for label, a, b, ratio in rows:
        print(f"{label:<26}{a:>14,.2f}{b:>14,.2f}{ratio:>11.2f}x")

    print()
    print(f"UUIDv7 writes {v4['insert_s'] / v7['insert_s']:.2f}x faster and stores the same "
          f"{ROWS:,} rows in {(1 - v7['file_bytes'] / v4['file_bytes']) * 100:.1f}% less disk.")


if __name__ == "__main__":
    main()
