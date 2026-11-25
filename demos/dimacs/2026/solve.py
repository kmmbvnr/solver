"""Minimum-cost flow on a directed network (DIMACS .min)."""
from math import isfinite
from time import monotonic

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


def problem(stream):
    arcs = []
    for line in stream:
        fields = line.split()
        if not fields or fields[0] == "c":
            continue
        if fields[:2] == ["p", "min"]:
            n, m = map(int, fields[2:])
            supply = np.zeros(n)
        elif fields[0] == "n":
            node, value = map(int, fields[1:])
            supply[node - 1] = value
        elif fields[0] == "a":
            arcs.append(tuple(map(int, fields[1:])))
        else:
            raise ValueError(line)
    if len(arcs) != m:
        raise ValueError("arc count mismatch")
    rows, signs, columns = [], [], []
    for i, (a, b, low, high, cost) in enumerate(arcs):
        rows.extend((a - 1, b - 1))
        columns.extend((i, i))
        signs.extend((1, -1))
    matrix = coo_matrix((signs, (rows, columns)), shape=(n, m)).tocsc()
    costs = [arc[4] for arc in arcs]
    bounds = [(low, high) for _, _, low, high, _ in arcs]

    def minimize(plan, deadline):
        options = {"time_limit": max(0., deadline - monotonic())} if isfinite(deadline) else {}
        result = linprog(costs, A_eq=matrix, b_eq=supply, bounds=bounds, method="highs", options=options)
        if result.status == 1:
            return None
        if not result.success:
            raise ValueError(result.message)
        return {"cost": result.fun, "flows": result.x.tolist()}

    return [minimize], lambda plan: plan["cost"]
