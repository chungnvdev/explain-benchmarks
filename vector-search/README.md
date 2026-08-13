# Vector search: exact scan vs probing a few clusters (IVF)

Exact nearest-neighbour search compares the query against every stored vector. It is always
right, and it costs the whole collection on every single query.

An IVF index groups the vectors into clusters once. A query then ranks the cluster centroids
and only opens the `nprobe` closest ones, so it compares against roughly `nprobe / nlist` of
the collection. That is where the speed comes from — and where the misses come from, when the
true neighbour sits in a cluster that was not opened.

This benchmark implements both, in the standard library, and reports **recall next to speed**.

## Run it

```bash
python3 benchmark_vector.py
```

Pure Python 3, nothing installed — no numpy, no faiss. That caps the collection at 20,000
vectors, and it is why the millisecond figures are much slower than a real C library. The
comparison that survives is the **ratio between the two search methods in the same run**.

## What the corpus is

Synthetic embeddings with the property that makes indexing possible at all: a **low intrinsic
dimension**. Points are drawn in 8 latent dimensions around 40 topic centres, projected up to
64 dimensions with a fixed random matrix, jittered and normalised.

This matters. Sampling isotropic gaussian noise directly in 64 dimensions produces a corpus
with no local neighbourhood structure — measured on that version, nprobe=1 recall was 11%, and
no index could have done better. Real text embeddings are clumpy, which is exactly why cluster
based indexes work on them.

## Measured results

20,000 vectors · 64 dims · 128 clusters · 30 queries · top-10

| Search | ms / query | recall@10 | Vectors compared | Speedup |
|---|---|---|---|---|
| Exact scan | 23.1 | **100.0%** | 20,000 | 1.0x |
| IVF nprobe=1 | **0.39** | 45.7% | 174 (0.9%) | **58.8x** |
| IVF nprobe=4 | 1.26 | 84.3% | 709 (3.5%) | 18.3x |
| IVF nprobe=16 | **4.14** | **98.7%** | 2,588 (12.9%) | **5.6x** |
| IVF nprobe=32 | 8.55 | 99.7% | 5,138 (25.7%) | 2.7x |

Index build cost: 5.6 s, paid once before any query.

The headline "58x faster" is real and useless on its own: at that setting the search returns
fewer than half of the correct neighbours, with no error and no warning. One notch wider —
nprobe=16 — still gives 5.6x at 98.7% recall.

The number to ask for is not "how fast", it is **"how fast at what recall"**.

Raw output: [result.txt](result.txt)
