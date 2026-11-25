# DIMACS 2014 · Steiner tree in graphs

Read an undirected SteinLib `.stp` graph with nonnegative edge weights and terminal records. Build shortest-path trees from two candidate terminals, prune unused branches and retain the cheaper tree.

The example connects three terminals at cost 3. On SteinLib B01 the returned tree cost 82. Its edges, connectivity and cost were independently checked. [Source](https://steinlib.zib.de/download.php).

From the repository root, run `python demos/dimacs/2014/solve.py` for the included example or append the path to an input file.

## More tracks

From the repository root, run `python demos/dimacs/2014/degree_tree/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://dimacs11.zib.de/competition.html).

| Track | Pipeline | Local result |
|---|---|---|
| [Degree-constrained Steiner tree (DCST)](degree_tree/solve.py) | Grow degree-limited trees with different edge priorities, then prune optional leaves. | TF101057-t3, cost 2,826. |
| [Rooted revenue tree with budget and hops (STPRBH)](budget_tree/solve.py) | Compare revenue and revenue-per-cost path extensions. | B01-10-12, revenue 341, edge budget 35, hop limit 12. |
| [PCSPG, RPCST and MWCS](prize_tree/solve.py) | Compare a single vertex with profit-pruned shortest-path trees. STP terminal records select the objective. | a14000RandGraph_1_5, PCSPG cost 10,227.204976. i101M1, rooted PCST cost 109,271.502783 (root alone). drosophila001, connected vertex weight 17.265499. |

Use `prize_tree/unrooted.txt` and `prize_tree/node_weights.txt` to run the unrooted prize and node-weighted variants. The bundled default is rooted. The reported trees were replayed against the original edge lists, terminal constraints and objectives.
