# ShiftOpt

ShiftOpt is a general-purpose discrete optimization solver. We develop our own heuristics and benchmark them on competition problems.

Install the solver with `python -m pip install .`. To run the demos, use `python -m pip install '.[roadef]'`.

Compose heuristics with `run_pipeline(steps, score, seconds=limit)`. Each step receives the best plan so far (initially `None`) and a shared monotonic deadline. It returns a feasible proposal or `None`. The pipeline retains the plan with the lowest score. Choose the steps and their order explicitly. The glass-cutting demo combines constructors, repair, and `beam_search`, which keeps several partial solutions at each decision and lets the caller define how to extend and rank them.

## ROADEF/EURO benchmarks

Ranks show where ShiftOpt would place in the published standings.

| Year | Problem | Rank |
|---|---|---|
| [2016](demos/roadef/2016/) | Inventory routing | 4th of 10 |
| [2018](demos/roadef/2018/) | Glass cutting | 7th of 20 |
| [2020](demos/roadef/2020/) | Maintenance scheduling | 13th of 14 |
| [2022](demos/roadef/2022/) | Truck loading | 14th of 16 |
| [2026](demos/roadef/2026/) | Traffic routing | Sprint: joint 30th of 54. Qualification: joint 31st of 74. |
