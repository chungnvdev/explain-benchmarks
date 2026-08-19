# Load balancing: round robin is fair, and fair is not fast

Round robin hands request N to server N % k. Perfectly even **by count**. Real traffic is not
even **by cost**: most requests are cheap, a few are very expensive. So the rotation keeps
posting new work to a server that is still grinding through a heavy request, while its
neighbours sit idle.

Three strategies over the exact same arrival stream and the exact same service times:

| | how it picks |
|---|---|
| round robin | next server in the rotation (nginx default) |
| least connections | the server with the least outstanding work (`least_conn`) |
| power of two | pick 2 servers at random, use the less loaded one (`random two`) |

## Run it

```bash
python3 benchmark_lb.py
```

Pure Python 3 standard library, fixed seed. It is a discrete-event queue simulation, not a load
test against real servers: it schedules arrivals, assigns each to a server, and measures how
long requests waited before service started.

## Measured results

4 servers · 20,000 requests · offered load 77.9% of capacity · 94% of requests cost 8 ms,
6% cost 220 ms.

| Strategy | wait p50 | wait p95 | wait p99 | worst |
|---|---|---|---|---|
| Round robin | 137.2 ms | 773.3 ms | **1,201.0 ms** | 2,094.5 ms |
| Least connections | **5.5 ms** | 183.2 ms | **289.8 ms** | 433.1 ms |
| Power of two | 18.0 ms | 301.6 ms | 438.0 ms | 777.3 ms |

Median wait drops **25x**, p99 drops **4.1x** — same servers, same traffic, one config line.

Load matters: the first run of this benchmark was accidentally set at 101.3% of capacity, where
every strategy drowns and the numbers just measure how long you ran it. 77.9% is a realistic
operating point.

Raw output: [result.txt](result.txt)
