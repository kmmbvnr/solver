"""Reoptimize an ordered series of linear MIPs with warm starts and dual bounds."""

import argparse
import json
from functools import partial
from math import isfinite
from pathlib import Path
from time import monotonic

import highspy as hs
import numpy as np

from shiftopt import run_pipeline
from shiftopt.mip import LinearInstance
from shiftopt.model import _run_checked


def reuse(plan, deadline, instance, previous):
    if previous is None:
        return None
    seed = np.asarray(previous).clip(instance.lower, instance.upper)
    return instance.repair(seed, monotonic() + max(0.0, deadline - monotonic()) * 0.2)


def optimize(plan, deadline, instance, previous, bounds):
    model = instance.model
    seed = plan if plan is not None else previous
    if seed is not None:
        model.setSolution(len(seed), list(range(len(seed))), seed)
    model.setOptionValue("time_limit", max(0.0, deadline - monotonic()))
    _run_checked(model, max(0.0, deadline - monotonic()))
    info = model.getInfo()
    status = model.getModelStatus()
    if status == hs.HighsModelStatus.kOptimal:
        bounds.append(info.objective_function_value)
    elif len(instance.integer) and info.valid and isfinite(info.mip_dual_bound):
        bounds.append(info.mip_dual_bound)
    sol = model.getSolution()
    return sol.col_value if sol.value_valid and instance.valid(sol.col_value) else None


def solve(paths, seconds=30):
    results = []
    previous = None
    for path in paths:
        instance = LinearInstance(path)
        seed = [previous[v] for v in instance.names] if previous is not None else None
        bounds = []
        steps = [
            partial(reuse, instance=instance, previous=seed),
            partial(optimize, instance=instance, previous=seed, bounds=bounds),
        ]
        plan = run_pipeline(steps, instance.score, seconds=seconds)
        entry = instance.result(plan)
        entry.update(instance=path.name, dual_bound=bounds[-1] if bounds else None)
        previous = entry["solution"]
        results.append(entry)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instances", type=Path, nargs="*")
    parser.add_argument("--seconds", type=float, default=30, help="per model")
    args = parser.parse_args()
    paths = args.instances or sorted(Path(__file__).parent.glob("*.mps"))
    print(json.dumps(solve(paths, args.seconds), allow_nan=False))
