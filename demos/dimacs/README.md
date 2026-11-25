# DIMACS Implementation Challenges

One runnable problem from each of the 13 editions. Directory names use the edition's starting year in the [DIMACS archive](https://dimacs.rutgers.edu/programs/implementation-challenges/).

From the repository root:

```sh
python -m pip install .
python demos/dimacs/run.py 1992
python demos/dimacs/run.py 2001 pr1002.tsp --seconds 30
```

The optional time budget starts after input parsing. It is cooperative: an indivisible exact step can finish past the deadline.

Each run passes the edition's steps to `shiftopt.run_pipeline` and emits JSON containing the solution and the minimized pipeline score. Maximization uses a negative score. For exact queries with a prescribed answer, the score is zero and the answer is in `solution`. Each folder has an original example and records the input format and local verification results. The results describe individual instances, without a contest ranking.

| Edition | Years | Problem |
|---|---|---|
| 1 | [1990–1991](1990/) | Maximum flow |
| 2 | [1992–1993](1992/) | Graph coloring |
| 3 | [1993–1994](1993/) | Parallel connected components |
| 4 | [1994–1995](1994/) | Sorting by signed reversals |
| 5 | [1995–1996](1995/) | Minimum-priority queues |
| 6 | [1998](1998/) | Euclidean near-neighbor search |
| 7 | [2000](2000/) | Max-Cut semidefinite relaxation |
| 8 | [2001](2001/) | Euclidean traveling salesman |
| 9 | [2005–2006](2005/) | Single-source shortest paths |
| 10 | [2012](2012/) | Balanced graph partitioning |
| 11 | [2014](2014/) | Steiner tree in graphs |
| 12 | [2020–2022](2020/) | Inventory routing |
| 13 | [2026–2027](2026/) | Minimum-cost flow |
