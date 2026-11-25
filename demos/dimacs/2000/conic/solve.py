"""Compute and improve feasible primal points in real SeDuMi conic programs."""

import argparse
import json
from pathlib import Path
from time import monotonic

import cvxpy as cp
import numpy as np
from scipy.io import loadmat
from scipy.sparse import csr_matrix, issparse

from shiftopt import run_pipeline

matrix = rhs = costs = point = None
cones = []


def vector(value):
    return np.asarray(
        value.toarray() if issparse(value) else value, dtype=float
    ).reshape(-1)


def read_instance(path):
    global matrix, rhs, costs, point, cones
    data = loadmat(path, squeeze_me=True, struct_as_record=False)
    rhs, costs = vector(data["b"]), vector(data["c"])
    matrix = csr_matrix(data["A"]) if "A" in data else csr_matrix(data["At"]).T
    if matrix.shape != (rhs.size, costs.size):
        raise ValueError("inconsistent SeDuMi matrix dimensions")
    cone = data["K"]
    if any(np.any(getattr(cone, k, 0)) for k in ("xcomplex", "scomplex", "ycomplex")):
        raise ValueError("expected real cones")
    point = cp.Variable(len(costs))
    cones = [matrix @ point == rhs]
    offset = 0
    for kind in ("f", "l", "q", "r", "s"):
        for size in np.atleast_1d(getattr(cone, kind, [])).astype(int):
            if not size:
                continue
            length = int(size) ** 2 if kind == "s" else int(size)
            block = point[offset : offset + length]
            if kind == "l":
                cones.append(block >= 0)
            elif kind == "q":
                cones.append(cp.SOC(block[0], block[1:]))
            elif kind == "r":
                cones.append(
                    cp.SOC(
                        block[0] + block[1],
                        cp.hstack([block[0] - block[1], np.sqrt(2) * block[2:]]),
                    )
                )
            elif kind == "s":
                mat = cp.reshape(block, (int(size), int(size)), order="F")
                cones.extend([mat == mat.T, mat >> 0])
            offset += length
    if offset != len(costs):
        raise ValueError("cone sizes do not cover the primal vector")


def propose(plan, deadline, objective, seconds):
    if seconds <= 0:
        return None
    problem = cp.Problem(cp.Minimize(objective), cones)
    options = {} if not np.isfinite(seconds) else {"time_limit_secs": seconds}
    try:
        problem.solve(solver="SCS", eps=1e-7, **options)
    except cp.error.SolverError:
        return None
    if point.value is None or not np.isfinite(point.value).all():
        return None
    if any(np.max(np.abs(c.violation()), initial=0) > 1e-5 for c in cones):
        return None
    return point.value.tolist()


def feasible(plan, deadline):
    return propose(plan, deadline, 0, (deadline - monotonic()) / 2)


def minimize(plan, deadline):
    return propose(plan, deadline, costs @ point, deadline - monotonic())


def score(plan):
    return float(costs @ plan)


def solve(path, seconds=30.0):
    read_instance(path)
    plan = run_pipeline([feasible, minimize], score, seconds=seconds)
    if plan is None:
        raise ValueError("no primal point within the feasibility tolerance")
    return {"solution": plan, "pipeline_score": score(plan)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.mat"),
    )
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    print(json.dumps(solve(args.instance, args.seconds), allow_nan=False))
