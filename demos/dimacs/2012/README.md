# DIMACS 2012 · Balanced graph partitioning

Read unweighted undirected METIS adjacency lists. Breadth-first traversal initializes two parts differing in size by at most one. Pair swaps preserve the balance and reduce crossing edges. The solution lists one part ID per vertex.

The example has two parts of size three and one crossing edge. The bisection of a 5,000-vertex path also cut one edge. [Source](https://dimacs.rutgers.edu/programs/implementation-challenges/).

From the repository root, run `python demos/dimacs/2012/solve.py` for the included example or append the path to an input file.

## More tracks

From the repository root, run `python demos/dimacs/2012/kway/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://sites.cc.gatech.edu/dimacs10/data/dimacs10-rules.pdf).

| Track | Pipeline | Local result |
|---|---|---|
| [Balanced k-way partitioning](kway/solve.py) | Compare balanced traversal orders for edge cut or maximum communication volume. Use --parts K and --objective cut or volume. | Maximum communication volume 1 with two parts. |
| [Modularity clustering](clustering/solve.py) | Move vertices between neighboring communities in forward and reverse order. | Two triangles joined by a bridge, modularity 5/14. |
| [Mix clustering](mix/solve.py) | Compare label propagation orders subject to both coverage thresholds. Rank feasible candidates locally by performance, density, conductance, then expansion. | Performance 14/15, minimum density 1, mean conductance 1/7, mean expansion 1/3. |

The three new examples accept simple unweighted METIS graphs. The Mix demo reports all four metrics. The contest combines ranks across competitors and measures work separately for Pareto scoring.
