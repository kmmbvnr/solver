# DIMACS 1992–1993 · Graph coloring

Read a DIMACS `.col` edge list. Try largest-degree first, saturation-degree coloring and recoloring by color class. The output assigns one positive color to each vertex in input ID order.

The triangle in the example requires three colors. On `queen8_8.col` the pipeline used 12 colors, compared with the published value of 9. All 728 undirected edges were checked. [Source](https://mat.tepper.cmu.edu/COLOR/instances.html).

From the repository root, run `python demos/dimacs/1992/solve.py` for the included example or append the path to an input file.

## More tracks

From the repository root, run `python demos/dimacs/1992/clique/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://archive.dimacs.rutgers.edu/Challenges/).

| Track | Pipeline | Local result |
|---|---|---|
| [Maximum clique](clique/solve.py) | Degree order, then destroy and regrow the clique. | Eight mutually adjacent vertices on queen8_8. |
| [Satisfiability](sat/solve.py) | Compare a majority assignment with a seeded random walk on unsatisfied clauses. | All four bundled clauses satisfied. A positive residual returns UNKNOWN. |
