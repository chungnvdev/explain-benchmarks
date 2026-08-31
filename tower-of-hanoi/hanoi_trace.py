"""Tower of Hanoi — the exact move trace used in the video, plus how 2^n grows.

Part 1 prints every move for n=5 (the 31 moves you see in the video), with the
call-stack depth and per-disk move counts.
Part 2 solves bigger towers and times them, so you can watch 2^n - 1 take off.

Run it:
    python3 tower-of-hanoi/hanoi_trace.py
"""

import sys
import time

sys.setrecursionlimit(100)  # depth never exceeds n; keep the default honest


def solve(n, source, target, spare, on_move):
    """Canonical recursive solution: 3 lines of real work."""
    if n == 0:
        return
    solve(n - 1, source, spare, target, on_move)
    on_move(n, source, target)
    solve(n - 1, spare, target, source, on_move)


def trace(n):
    """Solve an n-disk tower and record every move."""
    moves = []
    solve(n, "A", "C", "B", lambda d, s, t: moves.append((d, s, t)))
    return moves


def main():
    # ---- Part 1: the tower from the video (n = 5) ----
    n = 5
    moves = trace(n)
    print(f"Tower of Hanoi, n = {n} disks, A -> C")
    print(f"total moves: {len(moves)}  (2^{n} - 1 = {2**n - 1})")
    print()
    for i, (disk, src, dst) in enumerate(moves, 1):
        depth = n - disk + 1  # call chain is always hanoi(5) -> ... -> hanoi(disk)
        print(f"move {i:2d}: disk {disk}  {src} -> {dst}   (call depth {depth})")
    print()
    counts = {d: sum(1 for m in moves if m[0] == d) for d in range(1, n + 1)}
    for d in range(1, n + 1):
        print(f"disk {d} moved {counts[d]:2d} times  (2^(n-k) = {2 ** (n - d)})")

    # ---- Part 2: watch 2^n grow ----
    print()
    print("bigger towers (move counting only):")
    for size in (5, 10, 15, 20, 24):
        count = 0

        def bump(_d, _s, _t):
            nonlocal count
            count += 1

        t0 = time.perf_counter()
        solve(size, "A", "C", "B", bump)
        dt = time.perf_counter() - t0
        print(f"n = {size:2d}: {count:>10,} moves  solved in {dt * 1000:10.1f} ms")
    print()
    print("every extra disk doubles the work — 64 disks would need 2^64 - 1 moves,")
    print("about 585 billion years at one move per second.")


if __name__ == "__main__":
    main()
