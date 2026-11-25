# ShiftOpt

ShiftOpt is a general-purpose discrete optimization solver. We develop our own heuristics and benchmark them on competition problems.

Install the solver with `python -m pip install .`. To run the demos, use `python -m pip install '.[roadef]'`.

## How the solver works

Each demo supplies named steps and a score to minimize. By default the engine runs the steps once in order. A demo can also supply a policy that picks the next step from a fixed list. It can repeat a step or stop early.

```mermaid
flowchart TD
    Start(["Start with an optional plan"]) --> Pick{"How is the next step chosen?"}
    Pick -->|Fixed order| Next["Take next in sequence<br/>Step 1 → Step 2 → … → Step N"]
    Pick -->|Policy| Choose["Read best plan, trial history<br/>and remaining time"]
    Next -->|Step available| Run["Run step with best plan and deadline"]
    Choose -->|Selected step| Run
    Run <-->|Optional model solve| Ext["External solver<br/>HiGHS or CP-SAT"]
    Run --> Keep["Keep first feasible plan or strict improvement"]
    Keep --> Pick
    Next -->|Sequence exhausted| End(["Return best plan"])
    Choose -->|Policy stops| End
    Pick -->|Time or step budget spent| End
```

The engine owns the deadline, scoring and trial history. The demo defines its moves and when to select them. Each policy call sees which steps ran, whether their proposals were accepted and how long they took. Adaptive runs require a finite `max_steps`, including construction.

### Example: packing a bag

Pack as much weight as possible into a bag with capacity 12. The policy starts with greedy packing, tries beam search when time permits, and calls HiGHS if there is still room in the bag.

```python
from time import monotonic
from shiftopt import MAXIMIZE, Model, beam_search, quicksum, run_pipeline

weights = (2, 3, 8, 4)
capacity = 12

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

def pack_with_highs(best, deadline):
    model = Model()
    take = [model.addVar(vtype="B") for weight in weights]
    total = quicksum(weight * var for weight, var in zip(weights, take))
    model.addConstr(total <= capacity)
    if best is not None:
        model.addConstr(total >= sum(best))
    model.setObjective(total, MAXIMIZE)
    result = model.optimize(time_limit=max(0, deadline - monotonic()))
    if result.has_solution:
        return tuple(w for w, var in zip(weights, take) if result.value(var) > 0.5)
    return None

def choose_step(best, history, remaining):
    if best is None:
        return greedy
    if sum(best) == capacity:
        return None
    tried = {trial.step for trial in history}
    if pack_with_beam not in tried and remaining > 0.1:
        return pack_with_beam
    if pack_with_highs not in tried:
        return pack_with_highs
    return None

steps = [greedy, pack_with_beam, pack_with_highs]
plan = run_pipeline(steps, score=lambda bag: -sum(bag), seconds=5,
                    policy=choose_step, max_steps=4)
print(plan)  # (8, 4)
```

Greedy takes `(2, 3, 4)` for a total of 9. Inside beam search, `priority` ranks partial bags and `width=2` keeps two alternatives, yielding `(3, 8)` for 11. The last step gives HiGHS one binary variable per item and uses 11 as a lower bound. HiGHS finds `(8, 4)` for 12. The policy sees a full bag and stops. With weights `(6, 6)`, greedy fills the bag immediately and the policy stops after one trial.

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
