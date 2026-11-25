"""General-purpose LP rounding and mixed-integer neighborhood repair."""

import argparse
import json
from pathlib import Path

from shiftopt import run_pipeline
from shiftopt.mip import LinearInstance, MipTrace


def solve(path, seconds=30, output=None):
    instance = LinearInstance(path)
    trace = MipTrace(instance.result, output)
    plan = run_pipeline(
        [
            instance.bound_start,
            instance.improve_coordinates,
            instance.rounded,
            instance.trials,
            instance.improve_coordinates,
        ],
        instance.score,
        seconds=seconds,
        on_accept=trace,
    )
    return {**instance.result(plan), "improvements": trace.history}


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
