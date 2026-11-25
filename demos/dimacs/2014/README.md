# DIMACS 2014 · Steiner tree in graphs

Read an undirected SteinLib `.stp` graph with nonnegative edge weights and terminal records. Build shortest-path trees from two candidate terminals, prune unused branches and retain the cheaper tree.

The example connects three terminals at cost 3. On SteinLib B01 the returned tree cost 82. Its edges, connectivity and cost were independently checked. [Source](https://steinlib.zib.de/download.php).

From the repository root, run `python demos/dimacs/run.py 2014` for the included example or append the path to an input file.
