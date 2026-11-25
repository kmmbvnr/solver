# DIMACS 1990

From the repository root, run `python demos/dimacs/1990/general_matching/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://archive.dimacs.rutgers.edu/Challenges/).

| Track | Pipeline | Local result |
|---|---|---|
| [General matching](general_matching/solve.py) | Greedy matching, then a binary model. Maximize cardinality, then minimize cost. | Four vertices, two edges selected, cost 5. |

The later network-flow edition uses the same input conventions for its [flow and bipartite matching demos](../2026/). The general-graph demo uses DIMACS edge records with an optional integer cost.
