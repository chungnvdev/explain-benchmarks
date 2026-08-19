"""What an index gives you, and what it quietly takes back.

Everybody measures the good half: a point lookup goes from scanning the whole table to a
handful of page reads. This measures the whole bill on one real SQLite database:

  1. reads   — WHERE user_id = ?, with and without the index
  2. writes  — inserting the same rows into a table with 0, 1 and 3 indexes
  3. disk    — how much of the file the indexes occupy
  4. the case where the index LOSES — a range that matches a large slice of the table

Standard library only (sqlite3), fixed seed, deterministic data.

Run:  python3 benchmark_index_cost.py
"""

import os
import random
import sqlite3
import tempfile
import time

ROWS = 300_000
EXTRA_ROWS = 100_000
LOOKUPS = 300
USERS = 50_000
PAYLOAD = "x" * 60
WIDE_SHARE = 0.30      # the range query matches ~30% of the table
SEED = 20260821

DDL = ("CREATE TABLE events (id INTEGER PRIMARY KEY, user_id INTEGER, score INTEGER, "
       "created_at INTEGER, payload TEXT)")


def rows(rng, n, start=0):
    for i in range(start, start + n):
        yield (i + 1, rng.randrange(USERS), rng.randrange(1000), 1700000000 + i, PAYLOAD)


def db_mb(path):
    return os.path.getsize(path) / 1048576


def insert(con, data):
    t0 = time.perf_counter()
    con.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?)", data)
    con.commit()
    return time.perf_counter() - t0


def main():
    import sys
    print(f"python {'.'.join(map(str, sys.version_info[:3]))} · sqlite3 {sqlite3.sqlite_version}")
    print(f"{ROWS:,} rows · payload {len(PAYLOAD)} B · seed {SEED} · standard library only\n")

    with tempfile.TemporaryDirectory() as tmp:
        rng = random.Random(SEED)
        base = list(rows(rng, ROWS))
        extra = list(rows(rng, EXTRA_ROWS, start=ROWS))
        probes = [rng.randrange(USERS) for _ in range(LOOKUPS)]
        cutoff = int(1000 * (1 - WIDE_SHARE))   # score > cutoff matches ~30%

        # ---------- table WITHOUT index ----------
        p_plain = os.path.join(tmp, "plain.db")
        plain = sqlite3.connect(p_plain)
        plain.execute(DDL)
        plain.commit()
        write_plain = insert(plain, base)
        size_plain = db_mb(p_plain)

        t0 = time.perf_counter()
        for u in probes:
            plain.execute("SELECT id FROM events WHERE user_id = ?", (u,)).fetchall()
        read_plain = (time.perf_counter() - t0) * 1000 / LOOKUPS

        # ---------- same table WITH one index ----------
        p_idx = os.path.join(tmp, "indexed.db")
        idx = sqlite3.connect(p_idx)
        idx.execute(DDL)
        idx.commit()
        insert(idx, base)
        size_before_index = db_mb(p_idx)
        t0 = time.perf_counter()
        idx.execute("CREATE INDEX ix_user ON events (user_id)")
        idx.commit()
        build_index = time.perf_counter() - t0
        size_after_index = db_mb(p_idx)

        t0 = time.perf_counter()
        for u in probes:
            idx.execute("SELECT id FROM events WHERE user_id = ?", (u,)).fetchall()
        read_idx = (time.perf_counter() - t0) * 1000 / LOOKUPS

        # ---------- write cost: 0 vs 1 vs 3 indexes, same 100k rows ----------
        write_costs = {}
        for label, extra_ddl in (
            ("0 indexes", []),
            ("1 index", ["CREATE INDEX ix_u ON events (user_id)"]),
            ("3 indexes", ["CREATE INDEX ix_u ON events (user_id)",
                           "CREATE INDEX ix_s ON events (score)",
                           "CREATE INDEX ix_c ON events (created_at)"]),
        ):
            path = os.path.join(tmp, f"w-{len(extra_ddl)}.db")
            con = sqlite3.connect(path)
            con.execute(DDL)
            for d in extra_ddl:
                con.execute(d)
            con.commit()
            insert(con, base)                    # warm the table to a realistic size first
            write_costs[label] = insert(con, extra)
            con.close()
            os.remove(path)

        # ---------- where the index loses: a wide range ----------
        # The query must read a column the index does NOT carry (payload), otherwise SQLite
        # answers straight from a covering index and the comparison is meaningless.
        WIDE = "SELECT SUM(LENGTH(payload)) FROM events{hint} WHERE score > ?"
        plan = idx.execute("EXPLAIN QUERY PLAN " + WIDE.format(hint=""), (cutoff,)).fetchall()
        idx.execute("CREATE INDEX ix_score ON events (score)")
        idx.commit()
        plan_with = idx.execute(
            "EXPLAIN QUERY PLAN " + WIDE.format(hint=" INDEXED BY ix_score"), (cutoff,)).fetchall()

        def timed(sql, n=5):
            best = None
            for _ in range(n):
                t0 = time.perf_counter()
                idx.execute(sql, (cutoff,)).fetchall()
                dt = (time.perf_counter() - t0) * 1000
                best = dt if best is None else min(best, dt)
            return best

        wide_scan = timed(WIDE.format(hint=" NOT INDEXED"))
        wide_index = timed(WIDE.format(hint=" INDEXED BY ix_score"))
        matched = idx.execute("SELECT COUNT(*) FROM events WHERE score > ?", (cutoff,)).fetchone()[0]

        idx.close(); plain.close()

        # ---------------- report ----------------
        print("1. READS — SELECT id FROM events WHERE user_id = ?")
        print(f"   no index : {read_plain:8.3f} ms per lookup")
        print(f"   indexed  : {read_idx:8.3f} ms per lookup   -> {read_plain / read_idx:,.0f}x faster\n")

        print(f"2. WRITES — inserting the same {EXTRA_ROWS:,} rows")
        base_w = write_costs["0 indexes"]
        for label in ("0 indexes", "1 index", "3 indexes"):
            w = write_costs[label]
            print(f"   {label:<11}: {w:6.2f} s" + ("" if label == "0 indexes"
                  else f"   -> {(w / base_w - 1) * 100:+.0f}% slower"))
        print()

        print("3. DISK")
        print(f"   table only        : {size_before_index:7.2f} MB")
        print(f"   table + 1 index   : {size_after_index:7.2f} MB   "
              f"-> index costs {size_after_index - size_before_index:.2f} MB "
              f"({(size_after_index / size_before_index - 1) * 100:.0f}% bigger)")
        print(f"   building it took  : {build_index:7.2f} s\n")

        print(f"4. WHERE THE INDEX LOSES — WHERE score > {cutoff} matches {matched:,} rows "
              f"({matched / ROWS * 100:.0f}% of the table)")
        print(f"   full table scan   : {wide_scan:7.2f} ms")
        print(f"   forced index scan : {wide_index:7.2f} ms   "
              f"-> index is {wide_index / wide_scan:.1f}x SLOWER here")
        print(f"   sqlite's own plan without hints: {plan[0][-1]}")
        print(f"   plan when forced onto the index: {plan_with[0][-1]}\n")

        print("RESULT")
        print(f"{'metric':<34}{'without index':>16}{'with index':>14}")
        print(f"{'point lookup (ms)':<34}{read_plain:>16.3f}{read_idx:>14.3f}")
        print(f"{'insert 100k rows (s)':<34}{base_w:>16.2f}{write_costs['1 index']:>14.2f}")
        print(f"{'insert 100k rows, 3 indexes (s)':<34}{'':>16}{write_costs['3 indexes']:>14.2f}")
        print(f"{'database file (MB)':<34}{size_before_index:>16.2f}{size_after_index:>14.2f}")
        print(f"{'wide range query (ms)':<34}{wide_scan:>16.2f}{wide_index:>14.2f}")


if __name__ == "__main__":
    main()
