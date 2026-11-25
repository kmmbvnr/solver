"""Shrink a proven infeasible subsystem and produce MIPcc27 JSON certificates."""

import argparse
import json
import os
from functools import partial
from pathlib import Path
from time import monotonic

import highspy as hs
import numpy as np

from shiftopt import run_pipeline
from shiftopt.mip import LinearInstance, QuietHighs


def elements(instance):
    integers = set(instance.integer.tolist())
    active = {("row", i) for i in range(len(instance.row_lower))}
    active.update(("integrality", i) for i in integers)
    for i in range(len(instance.names)):
        if i not in integers:
            if np.isfinite(instance.lower[i]):
                active.add(("lower_bound", i))
            if np.isfinite(instance.upper[i]):
                active.add(("upper_bound", i))
    return active


def check(active, deadline, instance):
    model = QuietHighs()
    model.passModel(instance.model.getLp())
    model.setOptionValue("threads", 1)
    n = len(instance.names)
    indices = np.arange(n, dtype=np.int32)
    lower = np.full(n, -np.inf)
    upper = np.full(n, np.inf)
    integral = np.zeros(n, dtype=np.uint8)
    for kind, i in active:
        if kind in ("lower_bound", "integrality"):
            lower[i] = instance.lower[i]
        if kind in ("upper_bound", "integrality"):
            upper[i] = instance.upper[i]
        if kind == "integrality":
            integral[i] = 1
    model.changeColsBounds(n, indices, lower, upper)
    model.changeColsIntegrality(n, indices, integral)
    model.changeColsCost(n, indices, np.zeros(n))
    rows = [i for i in range(model.getNumRow()) if ("row", i) not in active]
    if rows:
        model.deleteRows(len(rows), rows)
    if monotonic() >= deadline:
        return False, None
    model.setOptionValue("time_limit", deadline - monotonic())
    model.run()
    status = model.getModelStatus()
    if status == hs.HighsModelStatus.kInfeasible:
        return True, None
    sol = model.getSolution()
    if status == hs.HighsModelStatus.kOptimal and sol.value_valid:
        return False, np.asarray(sol.col_value)
    return False, None


def initial(plan, deadline, instance):
    active = elements(instance)
    return active if check(active, deadline, instance)[0] else None


def shrink(plan, deadline, instance, grouped):
    if plan is None:
        return None
    ordered = sorted(plan)
    size = max(1, len(ordered) // 4) if grouped else 1
    best = plan
    for i in range(0, len(ordered), size):
        if monotonic() >= deadline:
            break
        trial = best.difference(ordered[i : i + size])
        if check(trial, deadline, instance)[0]:
            best = trial
    return best


def certificate(element, plan, deadline, instance):
    kind, i = element
    trial = plan - {element}
    if kind == "integrality":
        trial = trial | {("lower_bound", i), ("upper_bound", i)}
    _, x = check(trial, deadline, instance)
    if x is None:
        return None
    if kind == "integrality":
        violation = abs(x[i] - round(x[i]))
    elif kind == "lower_bound":
        violation = instance.lower[i] - x[i]
    elif kind == "upper_bound":
        violation = x[i] - instance.upper[i]
    else:
        value = (instance.matrix.getrow(i) @ x).item()
        violation = max(instance.row_lower[i] - value, value - instance.row_upper[i])
    if violation <= 1e-5:
        return None
    return {name: float(v) for name, v in zip(instance.names, x) if v != 0}


def solve(path, seconds=30):
    end = monotonic() + seconds
    instance = LinearInstance(path)
    sequence = [
        partial(initial, instance=instance),
        partial(shrink, instance=instance, grouped=True),
        partial(shrink, instance=instance, grouped=False),
    ]
    plan = run_pipeline(sequence, len, seconds=max(0.0, (end - monotonic()) * 0.85))
    if plan is None:
        raise ValueError("could not prove infeasibility within the budget")
    original = instance.model.getLp()
    rows = {}
    columns = {}
    for element in sorted(elements(instance)):
        kind, i = element
        item = {"action": "keep" if element in plan else "relax"}
        if element in plan and monotonic() < end:
            witness = certificate(element, plan, end, instance)
            if witness is not None:
                item["certificate"] = witness
        if kind == "row":
            rows[original.row_names_[i]] = item
        else:
            columns.setdefault(instance.names[i], {})[kind] = item
    for i in instance.integer:
        col = columns[instance.names[i]]
        if np.isfinite(instance.lower[i]):
            col["lower_bound"] = {"action": "relax"}
        if np.isfinite(instance.upper[i]):
            col["upper_bound"] = {"action": "relax"}
    return {"rows": rows, "columns": columns}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.mps"),
    )
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument(
        "--seconds",
        type=float,
        default=float(os.environ.get("MIPCC_TIME_LIMIT", 30)) * 0.95,
    )
    args = parser.parse_args()
    result = json.dumps(solve(args.instance, args.seconds), allow_nan=False)
    if args.output:
        args.output.write_text(result + "\n")
    else:
        print(result)
