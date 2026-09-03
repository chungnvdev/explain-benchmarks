"""Bubble sort — the exact trace behind the video, plus what O(n^2) costs for real.

Part 1 replays the video's 10-element array: every comparison and swap, the
per-pass "bubble up" locks, and the final counts (45 comparisons, 23 swaps).
Part 2 sorts growing random arrays with bubble sort vs Python's built-in
sorted() and times both, so you can feel the n^2 wall.

Run it:
    python3 bubble-sort/bubble_trace.py
"""

import random
import time

VIDEO_INPUT = [5, 9, 1, 7, 3, 10, 2, 8, 6, 4]  # locked array used in the video


def bubble_sort(a, on_compare=None, on_swap=None):
    """Canonical bubble sort (no early-exit): always n(n-1)/2 comparisons."""
    n = len(a)
    comparisons = swaps = 0
    for i in range(n - 1):
        for j in range(n - 1 - i):
            comparisons += 1
            if on_compare:
                on_compare(j, a[j], a[j + 1])
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swaps += 1
                if on_swap:
                    on_swap(j, a[j + 1], a[j])
    return comparisons, swaps


def main():
    # ---- Part 1: the array from the video ----
    a = VIDEO_INPUT.copy()
    print("input:", a)
    step = [0]

    def show_swap(j, hi, lo):
        step[0] += 1
        print(f"swap {step[0]:2d}: a[{j}]<->a[{j+1}]  ({hi} > {lo})   -> {a}")

    comparisons, swaps = bubble_sort(a, on_swap=show_swap)
    print("sorted:", a)
    print(f"comparisons: {comparisons}  (n(n-1)/2 = 45)   swaps: {swaps}")

    # ---- Part 2: the n^2 wall, measured ----
    print()
    print("bubble sort vs sorted() on random arrays (same data for both):")
    rng = random.Random(42)  # fixed seed: reruns give the same arrays
    for n in (1_000, 2_000, 4_000):
        data = [rng.random() for _ in range(n)]
        b = data.copy()
        t0 = time.perf_counter()
        comparisons, swaps = bubble_sort(b)
        t_bubble = time.perf_counter() - t0
        s = data.copy()
        t0 = time.perf_counter()
        s = sorted(s)
        t_sorted = time.perf_counter() - t0
        assert b == s
        print(
            f"n = {n:5,}: bubble {t_bubble * 1000:9.1f} ms ({comparisons:,} cmp)"
            f"   sorted() {t_sorted * 1000:6.2f} ms   ({t_bubble / t_sorted:,.0f}x slower)"
        )
    print()
    print("doubling n quadruples the comparisons — that is O(n^2) in one line.")


if __name__ == "__main__":
    main()
