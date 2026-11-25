# DIMACS 1990–1991 · Maximum flow

A directed DIMACS `.max` file supplies integer capacities and two terminals. ShiftOpt returns the maximum net outflow and one flow per arc in file order.

The example has maximum flow 9. A 5,000-vertex chain carried its full bottleneck capacity of 7. [Source](https://coral.ise.lehigh.edu/flow-challenge-2-0/mf-definition-and-format/).

From the repository root, run `python demos/dimacs/run.py 1990` for the included example or append the path to an input file.
