"""Vector search: scanning every embedding vs probing a few clusters (IVF).

Exact search compares the query against every stored vector — cost grows with the
collection. An IVF index groups vectors into clusters once, then a query only compares
against the clusters nearest to it. That is faster, and it can miss neighbours: the
number that matters is recall, not just milliseconds.

Pure standard library on purpose — no numpy, no faiss, nothing to install. That caps the
collection size, but every ratio below is measured on the same machine in the same run.

Run:  python3 benchmark_vector.py
"""

import math
import random
import time
from operator import mul

VECTORS = 20_000
DIM = 64
CLUSTERS = 128
KMEANS_SAMPLE = 6_000
KMEANS_ROUNDS = 5
QUERIES = 30
K = 10
PROBES = [1, 4, 16, 32]
SEED = 20260816
TOPICS = 40       # embeddings of real text are clumpy, not uniform noise — simulate topics
LATENT = 8          # intrinsic dimension: the manifold the embeddings really live on
TOPIC_SIGMA = 0.55  # spread inside one topic, in latent space
AMBIENT_NOISE = 0.15  # jitter added in the full 64-dim space
QUERY_SIGMA = 0.12  # a query sits near an existing item ("more like this"), not in empty space


def unit(v):
    n = math.sqrt(sum(map(mul, v, v))) or 1.0
    return [x / n for x in v]


def make_corpus(rng):
    """Synthetic embeddings with the property that matters here: a low intrinsic dimension.

    A real text embedder outputs 384 or 768 numbers, but the meaning lives on a much smaller
    manifold — that is why neighbours cluster at all. So: draw a latent point in LATENT dims
    (around one of TOPICS topic centres), project it up to DIM with a fixed random matrix, add
    a little ambient noise, normalise. Isotropic gaussian noise straight in 64 dims would have
    no local neighbourhood structure and no index could exploit it.
    """
    proj = [[rng.gauss(0, 1) for _ in range(LATENT)] for _ in range(DIM)]
    topic_centers = [[rng.gauss(0, 1) for _ in range(LATENT)] for _ in range(TOPICS)]
    out = []
    for i in range(VECTORS):
        tc = topic_centers[i % TOPICS]
        z = [tc[j] + rng.gauss(0, TOPIC_SIGMA) for j in range(LATENT)]
        x = [sum(map(mul, row, z)) + rng.gauss(0, AMBIENT_NOISE) for row in proj]
        out.append(unit(x))
    return out


def nearest_center(v, centers):
    best, best_score = 0, -2.0
    for i, c in enumerate(centers):
        s = sum(map(mul, v, c))
        if s > best_score:
            best, best_score = i, s
    return best, best_score


def build_ivf(data, rng):
    """k-means on a sample (cheap), then assign every vector to its nearest centroid."""
    t0 = time.perf_counter()
    centers = [data[rng.randrange(VECTORS)][:] for _ in range(CLUSTERS)]
    sample = [data[rng.randrange(VECTORS)] for _ in range(KMEANS_SAMPLE)]
    for _ in range(KMEANS_ROUNDS):
        sums = [[0.0] * DIM for _ in range(CLUSTERS)]
        counts = [0] * CLUSTERS
        for v in sample:
            ci, _ = nearest_center(v, centers)
            acc = sums[ci]
            for d in range(DIM):
                acc[d] += v[d]
            counts[ci] += 1
        for ci in range(CLUSTERS):
            if counts[ci]:
                centers[ci] = unit(sums[ci])
    lists = [[] for _ in range(CLUSTERS)]
    for idx, v in enumerate(data):
        ci, _ = nearest_center(v, centers)
        lists[ci].append(idx)
    return centers, lists, time.perf_counter() - t0


def exact_topk(q, data):
    scored = [(sum(map(mul, q, v)), i) for i, v in enumerate(data)]
    scored.sort(reverse=True)
    return [i for _, i in scored[:K]]


def ivf_topk(q, data, centers, lists, nprobe):
    ranked = sorted(((sum(map(mul, q, c)), ci) for ci, c in enumerate(centers)), reverse=True)
    scored = []
    visited = 0
    for _, ci in ranked[:nprobe]:
        for i in lists[ci]:
            scored.append((sum(map(mul, q, data[i])), i))
        visited += len(lists[ci])
    scored.sort(reverse=True)
    return [i for _, i in scored[:K]], visited


def main():
    print(f"python {'.'.join(map(str, __import__('sys').version_info[:3]))} · standard library only")
    print(f"{VECTORS:,} vectors · {DIM} dims · unit length (cosine = dot product)")
    print(f"IVF: {CLUSTERS} clusters · k-means on {KMEANS_SAMPLE:,} samples × {KMEANS_ROUNDS} rounds")
    print(f"{QUERIES} queries · top-{K} · recall measured against exact search\n")

    rng = random.Random(SEED)
    print("building corpus ...", flush=True)
    data = make_corpus(rng)
    # Queries that look like real ones: near an existing vector, not pure noise.
    queries = [unit([data[rng.randrange(VECTORS)][d] + rng.gauss(0, QUERY_SIGMA) for d in range(DIM)])
               for _ in range(QUERIES)]

    print("building IVF index ...", flush=True)
    centers, lists, build_s = build_ivf(data, rng)
    sizes = sorted(len(l) for l in lists)
    print(f"  index built in {build_s:.1f} s · cluster sizes: min {sizes[0]}, "
          f"median {sizes[len(sizes) // 2]}, max {sizes[-1]}\n")

    print("exact search (scan everything) ...", flush=True)
    truth = []
    t0 = time.perf_counter()
    for q in queries:
        truth.append(exact_topk(q, data))
    exact_ms = (time.perf_counter() - t0) * 1000 / QUERIES
    print(f"  {exact_ms:.1f} ms per query · {VECTORS:,} comparisons each\n")

    rows = []
    for nprobe in PROBES:
        t0 = time.perf_counter()
        hits, visited_total = 0, 0
        for qi, q in enumerate(queries):
            got, visited = ivf_topk(q, data, centers, lists, nprobe)
            visited_total += visited
            hits += len(set(got) & set(truth[qi]))
        ms = (time.perf_counter() - t0) * 1000 / QUERIES
        recall = hits / (QUERIES * K) * 100
        visited = visited_total / QUERIES
        rows.append((nprobe, ms, recall, visited))
        print(f"IVF nprobe={nprobe:<3} {ms:6.2f} ms/query · recall@{K} {recall:5.1f}% · "
              f"{visited:7.0f} vectors compared ({visited / VECTORS * 100:.1f}% of the collection) · "
              f"{exact_ms / ms:.1f}x faster", flush=True)

    print("\nRESULT")
    print(f"{'search':<18}{'ms/query':>10}{'recall@' + str(K):>12}{'vectors seen':>15}{'speedup':>10}")
    print(f"{'exact scan':<18}{exact_ms:>10.1f}{'100.0%':>12}{VECTORS:>15,}{'1.0x':>10}")
    for nprobe, ms, recall, visited in rows:
        print(f"{'IVF nprobe=' + str(nprobe):<18}{ms:>10.2f}{recall:>11.1f}%{visited:>15,.0f}"
              f"{exact_ms / ms:>9.1f}x")
    print(f"\nindex build cost: {build_s:.1f} s (paid once, before any query)")


if __name__ == "__main__":
    main()
