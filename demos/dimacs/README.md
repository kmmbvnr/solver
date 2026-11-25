# DIMACS Implementation Challenges

These benchmarks use multiple pipeline steps to compete on an objective or improve an incumbent. Directory names use the edition's starting year in the [DIMACS archive](https://dimacs.rutgers.edu/programs/implementation-challenges/).

From the repository root:

```sh
python -m pip install .
python demos/dimacs/run.py 1992
python demos/dimacs/run.py 2001 pr1002.tsp --seconds 30
```

The optional time budget starts after input parsing. It is cooperative: a running step can finish past the deadline.

Each run passes the edition's steps to `shiftopt.run_pipeline` and emits JSON containing the solution and the minimized pipeline score. Each folder has an original example and records the input format and local verification results. The results describe individual instances, without a contest ranking.

| Years | Problem | What the pipeline compares |
|---|---|---|
| [1992–1993](1992/) | Graph coloring | Degree order, saturation order and recoloring of the best plan |
| [1994–1995](1994/) | Signed reversals | Number of reversals when sorting from opposite ends |
| [2001](2001/) | Euclidean traveling salesman | Sweep and nearest-neighbor tours, followed by 2-opt on the shorter tour |
| [2012](2012/) | Balanced graph partitioning | Initial bisection and balanced vertex swaps scored by cut size |
| [2014](2014/) | Steiner tree | Cost of pruned trees grown from different root terminals |
| [2020–2022](2020/) | Inventory routing | Just-in-time and HiGHS replenishment plans, followed by route refinement |
