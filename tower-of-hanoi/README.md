# Tower of Hanoi

The exact move trace behind the video — every one of the 31 moves for 5 disks,
with the call-stack depth of each move — plus a second part that solves bigger
towers and times them, so you can watch 2^n − 1 take off.

```bash
python3 tower-of-hanoi/hanoi_trace.py
```

Measured on this machine (see `result.txt` for the raw run):

- n = 5: **31 moves** (2⁵ − 1) — disk 1 moves **16×**, disk 5 moves **once** (2^(n−k))
- n = 20: **1,048,575 moves** in ~77 ms
- n = 24: **16,777,215 moves** in ~1.2 s
- every extra disk doubles the work; 64 disks ≈ **585 billion years** at one move per second

Try `n = 6` or `7` in Part 1 and check the move count against 2^n − 1.
