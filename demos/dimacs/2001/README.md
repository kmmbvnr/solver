# DIMACS 2001 · Euclidean traveling salesman

Read TSPLIB `EUC_2D` coordinates. Compare a coordinate sweep and a nearest-neighbor tour, then apply three passes of bounded 2-opt. Distances use TSPLIB nearest-integer rounding. The final city connects back to the first.

The example tour has length 14. On `pr1002` the verified tour length was 294,209. The published optimum is 259,045, a gap of 13.6%. [Source](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSP-BEST.html).

From the repository root, run `python demos/dimacs/run.py 2001` for the included example or append the path to an input file.
