# PACE 2026

From this directory, run `python agreement_forest/solve.py` for the bundled example. Pass an instance path or `-` for standard input. The table uses `--seconds 5` on the listed public inputs.

| Demo | Public input | Measure | Result |
|---|---|---|---:|
| [Maximum agreement forest](agreement_forest/solve.py) | [tiny01.nw](https://pace2026.imada.sdu.dk/datasets/tiny02.tar) | components | 4 |

The pipeline isolates candidate leaves and extracts maximal common clades across the remaining trees. The published example for these trees also uses 4 components. The demo supplies a feasible forest without a certificate of optimality or approximation ratio. [Example forest](https://pacechallenge.org/2026/format/).

[Competition and tracks](https://pacechallenge.org/2026/).
