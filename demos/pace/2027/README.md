# PACE 2027

From this directory, run `python k_path/solve.py` for the bundled example. Pass an instance path or `-` for standard input. The table uses `--seconds 5` on the listed public inputs.

| Demo | Public input | Measure | Result |
|---|---|---|---:|
| [Unweighted k-path](k_path/solve.py) | [unweighted/sample-1.gr](https://pacechallenge.org/2027/files/tiny.zip) | path length | 4 |
| [Weighted directed k-path](k_path/solve.py) | [weighted/sample-1.gr](https://pacechallenge.org/2027/files/tiny.zip) | path weight | 12 |

The search matched the published objective on all 10 unweighted and 10 weighted tiny instances with a one-second budget per instance, including the weighted instance with no feasible path. A timed-out search with no witness reports failure. Use `k_path/weighted.txt` for the bundled weighted example.

[Competition and tracks](https://pacechallenge.org/2027/).
