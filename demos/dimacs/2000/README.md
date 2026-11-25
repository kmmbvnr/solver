# DIMACS 2000 · Max-Cut semidefinite relaxation

Read the torus `.dat` edge list with header `n m` followed by one-based endpoints and integer weights. Coordinate sweeps optimize unit vectors of dimension at most eight. Their Gram matrix is positive semidefinite with unit diagonal. The score uses the archive's half-Laplacian normalization in raw input weight units.

The triangle reaches 4.5 to numerical tolerance. On `toruspm3-8-50` (512 vertices), the feasible relaxation objective was 1055.126340. Each row norm and the objective were independently recomputed. The value is a primal estimate. [Source](https://archive.dimacs.rutgers.edu/Challenges/Seventh/Instances/).

From the repository root, run `python demos/dimacs/run.py 2000` for the included example or append the path to an input file.
