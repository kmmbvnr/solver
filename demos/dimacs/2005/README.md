# DIMACS 2005–2006 · Single-source shortest paths

Read a directed DIMACS `.gr` graph with nonnegative integer arc lengths. Dijkstra's algorithm starts at vertex 1 and returns distances in vertex ID order. Unreachable vertices have JSON value `null`.

Example distances are `0, 3, 2, 6, null`. Distances on a 5,000-node path matched the sum of its edge lengths at every vertex. [Source](https://www.diag.uniroma1.it/challenge9/).

From the repository root, run `python demos/dimacs/run.py 2005` for the included example or append the path to an input file.
