# DIMACS 1998 · Euclidean near-neighbor search

The demo text header gives the point count, query count and dimension. Supply one vector per line, data points first. A k-d tree returns the zero-based index and Euclidean distance of an exact nearest neighbor for each query. Ties may return any closest point.

Both example distances are 1. On 10,000 eight-dimensional points, all 64 query results matched exhaustive distance calculations. [Source](https://archive.dimacs.rutgers.edu/Challenges/Sixth/general.html).

From the repository root, run `python demos/dimacs/run.py 1998` for the included example or append the path to an input file.
