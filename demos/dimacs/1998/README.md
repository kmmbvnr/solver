# DIMACS 1998

From the repository root, run `python demos/dimacs/1998/approximate_neighbors/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://archive.dimacs.rutgers.edu/archive/Challenges/Sixth/).

| Track | Pipeline | Local result |
|---|---|---|
| [Approximate Euclidean nearest neighbors](approximate_neighbors/solve.py) | Refine each query with candidates from eight sorted random projections. Input is n, q, dimension, then the points and queries. | On 10,000 generated points in eight dimensions, 9 of 64 queries matched the exact neighbor. Output indices start at zero. |
