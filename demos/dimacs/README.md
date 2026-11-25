# DIMACS Implementation Challenges

These benchmarks use multiple pipeline steps to compete on an objective or improve an incumbent. Directory names use the edition's starting year in the [DIMACS archive](https://dimacs.rutgers.edu/programs/implementation-challenges/).

From the repository root:

```sh
python -m pip install .
python demos/dimacs/1992/solve.py
python demos/dimacs/2001/solve.py pr1002.tsp --seconds 30
```

The optional time budget starts after input parsing. It is cooperative: a running step can finish past the deadline.

Each run passes the edition's steps to `shiftopt.run_pipeline` and emits JSON containing the solution and the minimized pipeline score. Each solve script has a bundled input. The edition pages describe formats, options and checked results. The results describe individual instances, without a contest ranking.

| Edition | Implemented problem types |
|---|---|
| [1990–1991](1990/) | General matching. Shared network flow, assignment and bipartite matching implementations are under [2026](2026/). |
| [1992–1993](1992/) | Coloring, maximum clique, SAT |
| [1994–1995](1994/) | Sorting signed permutations by reversals |
| [1998](1998/) | Approximate nearest neighbors |
| [2000](2000/) | Torus max-cut relaxation and real SeDuMi linear, second-order and semidefinite programs |
| [2001](2001/) | Euclidean symmetric TSP and explicit asymmetric TSP |
| [2005–2006](2005/) | Single-source and point-to-point shortest paths |
| [2012](2012/) | Balanced edge cut, communication volume, modularity and Mix clustering |
| [2014](2014/) | All six contest variants: SPG, DCST, PCSPG, RPCST, MWCS and STPRBH |
| [2020–2022](2020/) | All eight routing tracks: CVRP, time windows, inventory, split delivery, electric, capacitated arc routing, time-dependent arc routing and dynamic ride-hailing |
| [2026–2027](2026/) | Minimum-cost flow, weighted assignment, maximum flow and s–t cut, bipartite matching, global minimum cut |

The 1993–1994 edition studied parallel implementations. Shortest paths and partitioning have standalone demos above. The 1995–1996 edition measured data structures. The 1994–1995 fragment assembly track is outside the signed-permutation demo. Coverage refers to problem types. File formats, supported variants and local results appear on each edition page.
