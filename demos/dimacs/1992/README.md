# DIMACS 1992–1993 · Graph coloring

Read a DIMACS `.col` edge list. Try largest-degree first, saturation-degree coloring and recoloring by color class. The output assigns one positive color to each vertex in input ID order.

The triangle in the example requires three colors. On `queen8_8.col` the pipeline used 12 colors, compared with the published value of 9. All 728 undirected edges were checked. [Source](https://mat.tepper.cmu.edu/COLOR/instances.html).

With `--reconstruct`, the shared assignment constructor tries to color the
graph with one fewer color than the incumbent. Assigning a color displaces
adjacent vertices of that color. Conflicts go back on the pending list. Each
color limit allows eight starts of at most eight placements per vertex.
On the same queen8_8 input and seed 1, reconstruction reduced 12 colors to
10, both with and without eviction history. Both colorings passed all 728 edge
checks. The published value is 9.

From the repository root, run `python demos/dimacs/1992/solve.py` for the included example or append the path to an input file.

## More tracks

From the repository root, run `python demos/dimacs/1992/clique/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://archive.dimacs.rutgers.edu/Challenges/).

| Track | Pipeline | Local result |
|---|---|---|
| [Maximum clique](clique/solve.py) | Degree order, then destroy and regrow the clique. | Eight mutually adjacent vertices on queen8_8. |
| [Satisfiability](sat/solve.py) | Compare a majority assignment with a seeded random walk on unsatisfied clauses. | All four bundled clauses satisfied. A positive residual returns UNKNOWN. |
