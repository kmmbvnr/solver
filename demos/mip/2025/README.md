# MIP 2025 · Quadratic primal heuristics

Install `python -m pip install '.[mip-quadratic]'` and run `python demos/mip/2025/solve.py [instance.mps] --seconds 20`. SCIP reads quadratic objectives and constraints. The first dive uses a continuous relaxation and fixes the integer variables closest to integers. A second dive uses a different fixing order and can refine the incumbent. Each candidate is replayed against the original SCIP model. JSON includes the time and objective of each accepted solution; `--solutions DIRECTORY` also writes their assignments.

The bundled model has optimal cost **−8**. On **Test_prob_76**, a twenty-second-budget run reached **0.62596737**, within **0.00000005** of the organizers' published reference **0.62596741**. Fixing the returned decision variables and solving the original model reproduced the objective. [Competition, instances and reference solutions](https://www.mixedinteger.org/2025/competition/).
