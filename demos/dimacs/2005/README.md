# DIMACS 2005

From the repository root, run `python demos/dimacs/2005/paths/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://www.diag.uniroma1.it/challenge9/).

| Track | Pipeline | Local result |
|---|---|---|
| [Single-source and point-to-point shortest paths](paths/solve.py) | Build a breadth-first path tree, then tighten it with weighted relaxation. Optional --source and --target. Reads nonnegative DIMACS .gr arcs. | Distances from vertex 1 are 0, 3, 2, 6 and unreachable. The certificate checks all edge inequalities. |
