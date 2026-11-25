# ShiftOpt

ShiftOpt is a general-purpose discrete optimization solver. We develop our own heuristics and benchmark them on competition problems.

Install the solver with `python -m pip install .`. To run the demos, use `python -m pip install '.[roadef]'`.

## How the solver works

Every demo defines its plan format, scoring function and step order. A step can build a plan from scratch, repair it or refine it. The same pipeline runs all five benchmarks.

```mermaid
sequenceDiagram
    participant D as Benchmark demo
    participant P as ShiftOpt pipeline
    participant H as Heuristic step
    participant S as External solver

    D->>P: run_pipeline(steps, score)
    loop For each step until the deadline
        P->>H: Best plan so far + deadline
        Note over H: Can use beam search, bounded flow<br/>or candidate selection
        opt Step needs a solver
            H->>S: Submit a subproblem to HiGHS or CP-SAT
            S-->>H: Subproblem result
        end
        H-->>P: Feasible plan or None
        Note over P: Keep the first plan and each<br/>strict improvement in score
    end
    P-->>D: Best plan found or None
```

### Example: packing a bag

Pack as much weight as possible into a bag with capacity 10. The greedy step takes items in order. The beam step starts a fresh search while the pipeline keeps the greedy plan.

```python
from shiftopt import beam_search, run_pipeline

weights = (6, 5, 5)
capacity = 10

def greedy(best, deadline):
    bag = ()
    for weight in weights:
        if sum(bag) + weight <= capacity:
            bag += (weight,)
    return bag

def pack_with_beam(best, deadline):
    def expand(state):
        i, bag = state
        yield i + 1, bag                       # Skip this item.
        if sum(bag) + weights[i] <= capacity:
            yield i + 1, bag + (weights[i],)   # Take this item.

    result = beam_search(
        (0, ()), expand,
        key=lambda state: (state[0], sum(state[1])),
        priority=lambda state: -sum(state[1]),
        complete=lambda state: state[0] == len(weights),
        width=2,
        deadline=deadline,
    )
    return result[1] if result is not None else None

plan = run_pipeline([greedy, pack_with_beam], score=lambda bag: -sum(bag), seconds=1)
print(plan)  # (5, 5)
```

Inside the beam step, `priority` ranks partial bags. Width 1 keeps the 6 and misses the pair of 5s. Width 2 also explores skipping the 6. Between steps, `score` ranks complete bags, so the pipeline replaces `(6,)` with `(5, 5)`.

## Core algorithms

- `beam_search` keeps the best partial plans at each search depth.
- `bounded_max_flow` maximizes flow subject to lower and upper edge bounds.
- `select_candidates` selects a high-value subset under resource limits, with optional learned resource prices from `PriceOracle`.
- `Calendar.eligible` filters job starts against resource and inventory limits.
- `Model.fixAndOptimize` fixes selected decisions and reoptimizes the rest with HiGHS.
- `Model.localBranch` searches with HiGHS within a limit on binary decision changes.

## ROADEF/EURO benchmarks

Ranks show where ShiftOpt would place in the published standings.

| Year | Problem | Rank |
|---|---|---|
| [2016](demos/roadef/2016/) | Inventory routing | 4th of 10 |
| [2018](demos/roadef/2018/) | Glass cutting | 7th of 20 |
| [2020](demos/roadef/2020/) | Maintenance scheduling | 13th of 14 |
| [2022](demos/roadef/2022/) | Truck loading | 14th of 16 |
| [2026](demos/roadef/2026/) | Traffic routing | Sprint: joint 30th of 54. Qualification: joint 31st of 74. |
