# PACE 2021

From this directory, run `python cluster_editing/solve.py` for the bundled example. Pass an instance path or `-` for standard input. The table uses `--seconds 5` on the listed public inputs.

| Demo | Public input | Measure | Result |
|---|---|---|---:|
| [Cluster editing](cluster_editing/solve.py) | [exact001.gr](https://fpt.akt.tu-berlin.de/pace2021/exact.tar.gz) | edge edits | 3 |
| [Kernelization](kernelization/solve.py) | [exact001.gr](https://fpt.akt.tu-berlin.de/pace2021/exact.tar.gz) | remaining vertices | 6 |

The official verifier accepted the three edits. The kernelization demo removes clique components with offset zero, renumbers the remaining vertices, and lifts all four prescribed edit sets to the original graph.

[Competition and tracks](https://pacechallenge.org/2021/).
