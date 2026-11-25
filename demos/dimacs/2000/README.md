# DIMACS 2000

From the repository root, run `python demos/dimacs/2000/torus/solve.py`. Each script accepts an input path and `--seconds`. [Edition and problem definitions](https://archive.dimacs.rutgers.edu/Challenges/Seventh/Instances/).

| Track | Pipeline | Local result |
|---|---|---|
| [Torus max-cut SDP relaxation](torus/solve.py) | Optimize a rank-one cut, then lift it to unit vectors and run coordinate descent. | toruspm3-8-50, 512 vertices, feasible SDP objective 1,055.170245. |
| [Real linear, second-order cone and semidefinite programs](conic/solve.py) | Read a SeDuMi MAT file, find a feasible primal point, then minimize cost with SCS. Acceptance tolerance is 1e-5 on each constraint. | truss5, primal cost 435.445202. Equality residuals and PSD block eigenvalues checked. |

Install the optional conic backend with `python -m pip install ".[dimacs-conic]"`. The conic example is a 2 × 2 positive semidefinite matrix with trace one. Some archive files are intentionally infeasible or numerically difficult. The demo only returns a primal point when its residual checks pass.
