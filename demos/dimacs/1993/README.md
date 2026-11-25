# DIMACS 1993–1994 · Parallel connected components

Read an undirected DIMACS edge list (`p edge` and `e` records). Up to four workers label separate edge blocks. A final merge labels the whole graph, including isolated vertices.

The example has three components. A generated 5,000-vertex graph consisting of 50 disjoint paths produced exactly 50 components. [Source](https://archive.dimacs.rutgers.edu/Volumes/Vol30.html).

From the repository root, run `python demos/dimacs/run.py 1993` for the included example or append the path to an input file.
