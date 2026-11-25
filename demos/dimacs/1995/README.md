# DIMACS 1995–1996 · Minimum-priority queues

The demo trace accepts `insert N` and `extract` on separate lines. Replay uses a binary heap and returns the extracted keys in order. Duplicate keys are allowed.

The example extracts `3, -1, 8, 8`. In a larger trace, 20,000 inserts followed by 20,000 extractions reproduced the sorted input. [Source](https://dimacs.rutgers.edu/programs/implementation-challenges/).

From the repository root, run `python demos/dimacs/run.py 1995` for the included example or append the path to an input file.
