# MIP 2026 · GPU-accelerated primal heuristics

Install `python -m pip install '.[mip-gpu]'` and run `python demos/mip/2026/solve.py [instance.mps.gz] --device auto --seconds 10`. The pipeline constructs bound and LP-rounding candidates. PyTorch evaluates batches of perturbed integer assignments against the sparse rows and objective. Shortlisted candidates get a double-precision feasibility check and, for mixed models, continuous LP repair. A final coordinate pass improves the best accepted solution. Use `--device cuda|mps|cpu` to select the backend and `--solutions DIRECTORY` to save improving assignments.

Local Apple GPU runs used ten seconds per public presolved instance. The MIPLIB checker accepted all three returned solutions. The reference column is the organizers' five-minute Gurobi run. Hardware and budgets differ.

| Instance | Local objective | Reference objective |
|---|---:|---:|
| instance_09 | 215 | 10 |
| instance_10 | 94 | 10 |
| instance_25 | −20 | −32 |
| instance_23 | No feasible solution found | 100.84 |
| instance_35 | No feasible solution found | 148 |
| instance_37 | No feasible solution found | 2 |

The bundled model costs **6**. [Competition, data and evaluation rules](https://www.mixedinteger.org/2026/competition/) · [Reference objectives](https://www.mixedinteger.org/2026/competition/instance_5m_bounds.txt).
