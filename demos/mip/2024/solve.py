"""Reduce a linear MIP and lift a reduced solution back to its original variables."""

import argparse
import gzip
import json
import shutil
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

import highspy as hs
import numpy as np

from shiftopt import run_pipeline
from shiftopt.mip import LinearInstance, QuietHighs


@dataclass
class Reduction:
    fixed: list
    redundant: list


def eliminate_fixed(plan, deadline, instance):
    valid = instance.lower == instance.upper
    ids = instance.integer
    valid[ids] &= instance.lower[ids] == np.rint(instance.lower[ids])
    fixed = np.flatnonzero(valid).tolist()
    # Keep one column so a completely fixed instance still has a portable MPS representation.
    if len(fixed) == len(instance.names):
        fixed = fixed[:-1]
    return Reduction(fixed, plan.redundant)


def remove_redundant(plan, deadline, instance):
    a = instance.matrix.tocsr()
    a.eliminate_zeros()
    positive = a.maximum(0)
    negative = a.minimum(0)
    positive.eliminate_zeros()
    negative.eliminate_zeros()
    low = positive @ instance.lower + negative @ instance.upper
    high = positive @ instance.upper + negative @ instance.lower
    rows = np.flatnonzero(
        (low >= instance.row_lower) & (high <= instance.row_upper)
    ).tolist()
    return Reduction(plan.fixed, rows)


def size(plan):
    return -(len(plan.fixed) + len(plan.redundant))


def solve(path, seconds=30):
    instance = LinearInstance(path)
    steps = [
        partial(eliminate_fixed, instance=instance),
        partial(remove_redundant, instance=instance),
    ]
    plan = run_pipeline(steps, size, initial=Reduction([], []), seconds=seconds)
    model = QuietHighs()
    model.passModel(instance.model.getLp())
    fixed = plan.fixed
    if fixed:
        values = instance.lower[fixed]
        shift = instance.matrix[:, fixed] @ values
        rows = np.arange(len(shift), dtype=np.int32)
        model.changeRowsBounds(
            len(rows), rows, instance.row_lower - shift, instance.row_upper - shift
        )
        model.changeObjectiveOffset(instance.offset + instance.cost[fixed] @ values)
        model.deleteCols(len(fixed), fixed)
    if plan.redundant:
        model.deleteRows(len(plan.redundant), plan.redundant)
    mapping = {instance.names[i]: float(instance.lower[i]) for i in fixed}
    return model, mapping


def write_model(model, path):
    if path.suffix == ".gz":
        with TemporaryDirectory() as folder:
            raw = Path(folder) / path.stem
            write_model(model, raw)
            with raw.open("rb") as src, gzip.open(path, "wb") as dst:
                shutil.copyfileobj(src, dst)
    elif model.writeModel(str(path)) == hs.HighsStatus.kError:
        raise OSError("could not write reduced model")


def lift(mapping, solution):
    if mapping.keys() & solution.keys():
        raise ValueError("reduced solution contains an eliminated variable")
    return {**solution, **mapping}


def read_solution(path):
    if path.suffix == ".json":
        record = json.loads(path.read_text())
        return (
            record.get("solution", record)
            if isinstance(record.get("solution"), dict)
            else record
        )
    values = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if fields and not line.lstrip().startswith("#") and fields[0] != "=obj=":
            name, value = fields
            values[name] = float(value)
    return values


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.mps"),
    )
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--reduced", type=Path, help="write the reduced MPS")
    parser.add_argument(
        "--mapping", type=Path, help="write fixed variable values as JSON"
    )
    parser.add_argument(
        "--postsolve", type=Path, nargs=2, metavar=("MAPPING", "SOLUTION")
    )
    args = parser.parse_args()
    if args.postsolve:
        map_path, sol_path = args.postsolve
        mapping = json.loads(map_path.read_text())
        solution = read_solution(sol_path)
        result = {"solution": lift(mapping, solution)}
    else:
        model, mapping = solve(args.instance, args.seconds)
        if args.reduced:
            write_model(model, args.reduced)
        if args.mapping:
            args.mapping.write_text(json.dumps(mapping))
        result = {
            "columns": model.getNumCol(),
            "rows": model.getNumRow(),
            "nonzeros": model.getNumNz(),
            "fixed": len(mapping),
        }
    print(json.dumps(result, allow_nan=False))
