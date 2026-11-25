# DIMACS 1992–1993 · Graph coloring

Read a DIMACS `.col` edge list. Try largest-degree first, saturation-degree coloring and recoloring by color class. The output assigns one positive color to each vertex in input ID order.

The triangle in the example requires three colors. On `queen8_8.col` the pipeline used 12 colors, compared with the published value of 9. All 728 undirected edges were checked. [Source](https://mat.tepper.cmu.edu/COLOR/instances.html).

From the repository root, run `python demos/dimacs/1992/solve.py` for the included example or append the path to an input file.
