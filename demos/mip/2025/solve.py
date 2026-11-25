"""Dive from a continuous relaxation and improve a checked quadratic MIP solution."""

import argparse
import gzip
import json
from functools import partial
from pathlib import Path
from time import monotonic

from pyscipopt import Model

from shiftopt import run_pipeline
from shiftopt.mip import MipTrace


def model_from(path):
    model = Model()
    model.hideOutput()
    model.readProblem(str(path))
    model.setRealParam("numerics/feastol", 1e-7)
    return model


def input_names(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    names = set()
    section = ""
    with opener(path, "rt") as stream:
        for line in stream:
            fields = line.split()
            if not fields or line.startswith("*"):
                continue
            if not line[0].isspace():
                section = fields[0]
            elif section == "COLUMNS" and "'MARKER'" not in fields:
                names.add(fields[0])
    return names


def fractionality(variable, center):
    value = center[variable.name]
    return abs(value - round(value))


def dive(plan, deadline, path, base, reverse):
    model = model_from(path)
    integers = [v for v in model.getVars() if v.vtype() != "CONTINUOUS"]
    if not integers:
        raise ValueError("expected integer variables")
    if plan is None:
        relaxation = model_from(path)
        for v in relaxation.getVars():
            if v.vtype() != "CONTINUOUS":
                relaxation.chgVarType(v, "C")
        relaxation.setRealParam("limits/time", max(0.0, (deadline - monotonic()) / 4))
        relaxation.optimize()
        sol = relaxation.getBestSol()
        if sol is None:
            return None
        center = {v.name: sol[v] for v in relaxation.getVars()}
    else:
        center = plan[1]
    if reverse:
        integers.reverse()
    integers.sort(key=partial(fractionality, center=center), reverse=reverse)
    for v in integers[: max(1, len(integers) // 2)]:
        value = round(center[v.name])
        if not v.getLbOriginal() <= value <= v.getUbOriginal():
            return None
        model.fixVar(v, value)
    model.setRealParam(
        "limits/time", max(0.0, (deadline - monotonic()) / (1 if reverse else 2))
    )
    model.optimize()
    sol = model.getBestSol()
    if sol is None:
        return None
    values = {v.name: float(sol[v]) for v in model.getVars(transformed=False)}
    replay = base.createOrigSol()
    for v in base.getVars(transformed=False):
        base.setSolVal(replay, v, values[v.name])
    if not base.checkSol(replay, original=True, printreason=False):
        return None
    return base.getSolObjVal(replay), values


def objective(plan, sign):
    return sign * plan[0]


def decode(plan, names):
    return {
        "objective": plan[0],
        "solution": {k: v for k, v in plan[1].items() if k in names},
    }


def solve(path, seconds=30, output=None):
    base = model_from(path)
    names = input_names(path)
    sign = 1 if base.getObjectiveSense() == "minimize" else -1
    trace = MipTrace(partial(decode, names=names), output)
    steps = [partial(dive, path=path, base=base, reverse=rev) for rev in (False, True)]
    plan = run_pipeline(
        steps, partial(objective, sign=sign), seconds=seconds, on_accept=trace
    )
    if plan is None:
        return {"solution": None, "objective": None, "improvements": trace.history}
    return {**decode(plan, names), "improvements": trace.history}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.mps"),
    )
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument(
        "--solutions", type=Path, help="directory for improving MIPLIB solution files"
    )
    args = parser.parse_args()
    print(
        json.dumps(
            solve(args.instance, args.seconds, output=args.solutions), allow_nan=False
        )
    )
