# ShiftOpt

ShiftOpt is a general-purpose discrete optimization solver. We develop our own heuristics and benchmark them on competition problems.

Install the solver with `python -m pip install .`. To run the demos, use `python -m pip install '.[roadef]'`.

Compose heuristics with `run_pipeline(steps, score, seconds=limit)`. Each step receives the best plan so far (initially `None`) and a shared monotonic deadline. It returns a feasible proposal or `None`. The pipeline retains the plan with the lowest score. Choose the steps and their order explicitly. The glass-cutting demo combines two constructors and a repair step.

- Inventory routing in [ROADEF/EURO 2016](demos/roadef/2016/).
- Glass cutting in [ROADEF/EURO 2018](demos/roadef/2018/).
- Traffic routing in [ROADEF/EURO 2026](demos/roadef/2026/).
