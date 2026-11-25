"""Run the selected DIMACS edition on its included example or a supplied input."""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from shiftopt import run_pipeline


def run(edition, instance, seconds=float("inf")):
    spec = importlib.util.spec_from_file_location("edition", edition / "solve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with instance.open() as stream:
        steps, score = module.problem(stream)
    plan = run_pipeline(steps, score, seconds=seconds)
    if plan is None:
        raise ValueError("no feasible solution returned within the search budget")
    return {"pipeline_score": score(plan), "solution": plan}


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", choices=sorted(p.parent.name for p in root.glob("*/solve.py")))
    parser.add_argument("instance", type=Path, nargs="?")
    parser.add_argument("--seconds", type=float, default=float("inf"), help="cooperative pipeline budget")
    args = parser.parse_args()
    folder = root / args.year
    # Native solvers can write directly to stdout before their logger is configured.
    with os.fdopen(os.dup(sys.stdout.fileno()), "w") as output:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        result = run(folder, args.instance or folder / "example.txt", args.seconds)
        print(json.dumps(result, allow_nan=False), file=output)
