# DIMACS 1994–1995 · Sorting by signed reversals

Enter a whitespace-separated signed permutation of `1..n`. Each output pair gives the inclusive, one-based endpoints of an interval to reverse and negate. Two greedy constructions fix entries from opposite ends. The pipeline keeps the shorter sequence.

The example takes one reversal, positions 2 through 4. Replaying the emitted intervals on a shuffled signed permutation of 2,000 integers recovered the identity. This heuristic gives a feasible reversal sequence. [Source](https://epubs.siam.org/doi/10.1137/S0097539793250627).

From the repository root, run `python demos/dimacs/run.py 1994` for the included example or append the path to an input file.
