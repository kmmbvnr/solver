# MIP 2022 · General-purpose primal heuristics

Run `python demos/mip/2022/solve.py [instance.mps.gz] --seconds 10` from the repository root after installing ShiftOpt. The pipeline tries variable bounds, takes improving coordinate moves, rounds an LP relaxation, and repairs integer assignments by reoptimizing their continuous variables. HiGHS solves the continuous subproblems. Use `--solutions DIRECTORY` to save improving assignments.

The bundled covering model costs 4. On the public **seymour** instance, the demo found a cover of cost **492** in a run with a ten-second budget. The MIPLIB checker accepted its integrality, constraints and objective. [Competition rules and public instances](https://www.mixedinteger.org/2022/competition/).
