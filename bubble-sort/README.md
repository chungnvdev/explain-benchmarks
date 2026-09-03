# Bubble sort

The exact trace behind the video — the same 10-element array, all 23 swaps
printed step by step (45 comparisons, 9 passes) — plus a timed part that pits
bubble sort against Python's built-in `sorted()` on growing arrays.

```bash
python3 bubble-sort/bubble_trace.py
```

Measured on this machine (see `result.txt` for the raw run, seed is fixed):

- video array `[5, 9, 1, 7, 3, 10, 2, 8, 6, 4]`: **45 comparisons, 23 swaps**
- n = 1,000: bubble **19.2 ms** vs `sorted()` **0.06 ms** (330x)
- n = 4,000: bubble **326.1 ms** vs `sorted()` **0.27 ms** (1,224x)
- comparisons 499,500 → 1,999,000 → 7,998,000: doubling n quadruples the work

Swap in your own array in `VIDEO_INPUT` and watch the swap count change —
it always equals the number of inversions.
