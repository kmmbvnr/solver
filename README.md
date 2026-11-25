# ShiftOpt

ShiftOpt is a general-purpose discrete optimization solver. We develop our own heuristics and benchmark them on competition problems.

Install the solver with `python -m pip install .`. To run the demos, use `python -m pip install '.[roadef]'`.

Every benchmark runs its search through `run_pipeline(steps, score)`. The demo supplies named steps in execution order and defines how to score a complete plan. A step receives the best plan so far (initially `None`) and a deadline. It returns a feasible proposal or `None`. The engine keeps the first feasible plan and each strict improvement. Steps can use beam search, bounded flow or an external solver. Step selection is currently manual.

## ROADEF/EURO benchmarks

Ranks show where ShiftOpt would place in the published standings.

| Year | Problem | Rank |
|---|---|---|
| [2016](demos/roadef/2016/) | Inventory routing | 4th of 10 |
| [2018](demos/roadef/2018/) | Glass cutting | 7th of 20 |
| [2020](demos/roadef/2020/) | Maintenance scheduling | 13th of 14 |
| [2022](demos/roadef/2022/) | Truck loading | 14th of 16 |
| [2026](demos/roadef/2026/) | Traffic routing | Sprint: joint 30th of 54. Qualification: joint 31st of 74. |
