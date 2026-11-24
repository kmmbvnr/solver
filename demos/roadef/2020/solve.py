"""Schedule maintenance starts under workload bounds and seasonal exclusions."""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
from instance import read
from refine import objective_value, refine
from repair import repair

from shiftopt import Model, quicksum, run_pipeline


class NoSchedule(RuntimeError):
    pass


def construct(data, seconds):
    model = Model(threads=1)
    loads = defaultdict(list)
    active = defaultdict(list)
    choices = {}
    objective = []
    for name, job in data["Interventions"].items():
        starts = [model.addVar(vtype="B") for _ in range(int(job["tmax"]))]
        choices[name] = starts
        model.addConstr(quicksum(starts) == 1)
        means = np.zeros(len(starts))
        for ids, vectors in job["risk"].values():
            means[ids] += vectors.mean(axis=1)
        objective.extend(c * v for c, v in zip(means, starts) if c)
        for start, var in enumerate(starts):
            for t in range(start, start + job["Delta"][start]):
                active[name, t].append(var)
        for resource, periods in job["workload"].items():
            for period, values in periods.items():
                loads[resource, int(period) - 1].extend(
                    value * starts[int(start) - 1]
                    for start, value in values.items()
                    if value
                )
    for resource, bounds in data["Resources"].items():
        for t, (lo, hi) in enumerate(zip(bounds["min"], bounds["max"])):
            terms = loads[resource, t]
            if terms:
                expr = quicksum(terms)
                model.addConstr(expr <= hi)
                if lo:
                    model.addConstr(expr >= lo)
            elif lo > 0:
                raise ValueError(f"No workload available for {resource} at {t + 1}")
    for first, second, season in data["Exclusions"].values():
        for period in data["Seasons"][season]:
            t = int(period) - 1
            if active[first, t] and active[second, t]:
                model.addConstr(quicksum(active[first, t] + active[second, t]) <= 1)
    model.setObjective(quicksum(objective))
    try:
        result = model.optimize(time_limit=seconds)
    except RuntimeError as error:
        raise NoSchedule("The start-date model did not produce a schedule") from error
    if not result.has_solution:
        raise NoSchedule(f"No feasible schedule found: {result.status}")
    return {
        name: next(i for i, v in enumerate(starts) if result.value(v) > 0.5)
        for name, starts in choices.items()
    }


def solve(instance, output, seconds, refine_seconds, repair_first=False, margins=True):
    data = read(instance)
    scenario_bytes = sum(
        v.nbytes
        for job in data["Interventions"].values()
        for _, v in job["risk"].values()
    )
    if repair_first or scenario_bytes > 750_000_000:
        plan = repair(data, seconds, margins)
    else:
        try:
            plan = construct(data, seconds)
        except NoSchedule:
            plan = repair(data, seconds, margins)
    if refine_seconds:
        plan = run_pipeline(
            [lambda incumbent, deadline: refine(data, incumbent, deadline)],
            lambda candidate: objective_value(data, candidate),
            initial=plan,
            seconds=refine_seconds,
        )
    with output.open("w") as stream:
        for name, start in plan.items():
            print(name, start + 1, file=stream)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=float, default=100)
    parser.add_argument("--refine-seconds", type=float, default=60)
    parser.add_argument(
        "--repair-first",
        action="store_true",
        help="construct by repairing conflicts directly",
    )
    parser.add_argument(
        "--plain-repair",
        action="store_true",
        help="use fixed conflict penalties and original capacities",
    )
    args = parser.parse_args()
    solve(
        args.instance,
        args.output,
        args.seconds,
        args.refine_seconds,
        args.repair_first,
        not args.plain_repair,
    )
