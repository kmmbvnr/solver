# DIMACS 2012 · Balanced graph partitioning

Read unweighted undirected METIS adjacency lists. Breadth-first traversal initializes two parts differing in size by at most one. Pair swaps preserve the balance and reduce crossing edges. The solution lists one part ID per vertex.

The example has two parts of size three and one crossing edge. The bisection of a 5,000-vertex path also cut one edge. [Source](https://dimacs.rutgers.edu/programs/implementation-challenges/).

From the repository root, run `python demos/dimacs/run.py 2012` for the included example or append the path to an input file.
