# DIMACS 2026

From the repository root, run `python demos/dimacs/2026/min_cost_flow/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://coral.ise.lehigh.edu/flow-challenge-2-0/).

| Track | Pipeline | Local result |
|---|---|---|
| [Minimum-cost flow](min_cost_flow/solve.py) | Compare a feasible integral flow with a cost-minimizing LP. Both enforce arc bounds and node balances. | Bundled network cost 14. A generated 5,000-node path cost 69,986. |
| [Weighted assignment and bipartite cardinality matching](matching/solve.py) | Greedy edges compete with sparse assignment. Dummy columns let vertices stay unmatched. Reads .asn or .bim. | Bundled weighted matching 14. cardinality.txt matches two pairs. |
| [Maximum flow and minimum s–t cut](max_flow/solve.py) | Forward augmentation builds a flow. Residual augmentation repairs it. A residual reachability test supplies a minimum-cut certificate when available. | Bundled network flow 2, cut capacity 2. |
| [Undirected global minimum cut](global_cut/solve.py) | Compare minimum-degree singleton cuts with cuts along traversal orders. Each arc record denotes one undirected edge. | Bundled two-triangle graph has cut weight 1. This heuristic gives an upper bound. |

For both flow demos, the solution lists integer flows in input arc order. The assignment demo maximizes total weight under the 2026 rules. Run it on `matching/cardinality.txt` for unweighted matching.
