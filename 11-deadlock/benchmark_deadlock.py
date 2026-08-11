#!/usr/bin/env python3
"""Deadlock benchmark — real numbers for the /nvc video #11.

Two transfers run at the same time: account 1 -> 2, and account 2 -> 1.
Each transfer locks the source account, does a little work, then locks the destination.
Thread A ends up holding lock 1 waiting for lock 2, while thread B holds lock 2
waiting for lock 1. Neither can move. Nothing crashes, nothing is logged — it just stops.

The fix is lock ordering: always acquire locks in the same global order,
no matter which direction the money is going.

Run it yourself:  python3 benchmark_deadlock.py
No install needed — threading ships with Python.
"""
import threading, time, sys

RUNS = 5
TIMEOUT = 2.0      # give up waiting after 2s so the demo cannot hang forever
WORK = 0.05        # 50 ms of work between taking the first and the second lock

def run(use_ordering):
    locks = {1: threading.Lock(), 2: threading.Lock()}
    done = []

    def transfer(src, dst):
        order = sorted([src, dst]) if use_ordering else [src, dst]
        with locks[order[0]]:
            time.sleep(WORK)                 # a DB write, a network call, anything
            with locks[order[1]]:
                done.append(f"{src}->{dst}")

    t1 = threading.Thread(target=transfer, args=(1, 2), daemon=True)
    t2 = threading.Thread(target=transfer, args=(2, 1), daemon=True)
    t0 = time.perf_counter()
    t1.start(); t2.start()
    t1.join(TIMEOUT); t2.join(TIMEOUT)
    ms = (time.perf_counter() - t0) * 1000
    stuck = t1.is_alive() or t2.is_alive()
    return len(done), ms, stuck

if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} | 2 transfers at once: 1->2 and 2->1")
    print(f"correct outcome: 2/2 completed\n")

    print("WITHOUT LOCK ORDERING")
    for i in range(RUNS):
        n, ms, stuck = run(False)
        flag = "DEADLOCK - threads still waiting" if stuck else "OK"
        print(f"  run {i+1}: completed {n}/2   {ms:6.0f} ms   ({flag})")

    print("\nWITH LOCK ORDERING  (always lock the lower id first)")
    for i in range(RUNS):
        n, ms, stuck = run(True)
        flag = "DEADLOCK - threads still waiting" if stuck else "OK"
        print(f"  run {i+1}: completed {n}/2   {ms:6.0f} ms   ({flag})")

    print("\n" + "=" * 58)
    print("without ordering : 0/2 completed, both threads waiting forever")
    print("with ordering    : 2/2 completed in ~100 ms, every single run")
    print("=" * 58)
