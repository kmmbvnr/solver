# PACE 2025

From this directory, run `python dominating_set/solve.py` for the bundled example. Pass an instance path or `-` for standard input. The table uses `--seconds 5` on the listed public inputs.

| Demo | Public input | Measure | Result |
|---|---|---|---:|
| [Dominating set](dominating_set/solve.py) | [ds/exact/exact_001.gr](https://github.com/MarioGrobler/PACE2025-instances) | selected vertices | 2106 |
| [Hitting set](hitting_set/solve.py) | [hs/exact/exact_001.hgr](https://github.com/MarioGrobler/PACE2025-instances) | selected vertices | 244 |

Both demos compare greedy covers with different tie orders. They use the same library step as the 2019 vertex-cover demo.

[Competition and tracks](https://pacechallenge.org/2025/).
