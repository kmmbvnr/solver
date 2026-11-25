# DIMACS 2001 · Euclidean traveling salesman

Read TSPLIB `EUC_2D` coordinates. Compare a coordinate sweep and a nearest-neighbor tour, then apply three passes of bounded 2-opt. Distances use TSPLIB nearest-integer rounding. The final city connects back to the first.

The example tour has length 14. On `pr1002` the verified tour length was 294,209. The published optimum is 259,045, a gap of 13.6%. [Source](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSP-BEST.html).

From the repository root, run `python demos/dimacs/2001/solve.py` for the included example or append the path to an input file.

## More tracks

From the repository root, run `python demos/dimacs/2001/asymmetric/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://archive.dimacs.rutgers.edu/archive/Challenges/TSP/).

| Track | Pipeline | Local result |
|---|---|---|
| [Asymmetric traveling salesman](asymmetric/solve.py) | Compare input order with a directed nearest-neighbor tour, then relocate cities. Reads a TSPLIB FULL_MATRIX. | br17, directed tour length 44. |
