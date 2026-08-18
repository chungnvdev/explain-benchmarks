# Safe retry: idempotency key + backoff jitter

"On error, retry three times" is one line of code and two separate ways to hurt yourself.

**Part A — the reply was lost, the work was not.** The server applied the write; only the
response died on the way back. The client sees nothing, assumes failure, and calls again. With
a non-idempotent write, every retry is another real record. The same run with a UNIQUE
idempotency key writes each intent exactly once.

**Part B — everyone retries on the same clock.** Clients that failed together retry together,
so a struggling server gets a spike instead of a trickle. AWS's *full jitter* —
`sleep = random(0, min(cap, base * 2 ** attempt))` — spreads the same retries over time.

## Run it

```bash
python3 benchmark_retry.py
```

Python 3 standard library only (sqlite3, random), fixed seed, nothing to install.

## Measured results

Part A — 500 payment intents, 18% of replies lost, up to 3 retries:

| | No idempotency key | UNIQUE idempotency key |
|---|---|---|
| Calls that reached the server | 608 | 608 |
| Rows written | **608** | **500** |
| Charged | **$30,400** | **$25,000** |
| Duplicate records | **108** (21.6% of intents) | 0 |

Part B — 2,000 clients fail at the same instant, 3 retries each (6,000 retries):

| Strategy | Peak per 100 ms window | Windows used |
|---|---|---|
| Fixed 1s / 2s / 3s | **2,000** | 3 |
| Full jitter | **369** | 40 |

Peak reduced by **5.4x**.

Part B schedules the retries and counts arrivals per window — it is a scheduling simulation,
not a load test against a real server. Part A writes to a real SQLite database.

Raw output: [result.txt](result.txt)
