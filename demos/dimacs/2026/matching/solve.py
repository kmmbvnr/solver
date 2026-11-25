"""Find maximum-weight assignments or maximum-cardinality bipartite matchings."""

import argparse
import json
from pathlib import Path
from time import monotonic

from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching

from shiftopt import run_pipeline

weights = {}
left = []
right = []


def score(plan):
    return -sum(weights[pair] for pair in plan)


def greedy(plan, deadline):
    used = set()
    result = []
    for pair in sorted(weights, key=weights.get, reverse=True):
        a, b = pair
        if monotonic() >= deadline or weights[pair] <= 0:
            break
        if a not in used and b not in used:
            result.append(pair)
            used.update(pair)
    return result


def optimal(plan, deadline):
    if not left or not right:
        return []
    row = {v: i for i, v in enumerate(left)}
    col = {v: i for i, v in enumerate(right)}
    # A private dummy column lets every left vertex stay unmatched.
    offset = 1 + max([0, *weights.values()])
    rows = list(range(len(left)))
    cols = [len(right) + i for i in rows]
    costs = [offset] * len(left)
    for (a, b), w in weights.items():
        if w > 0:
            rows.append(row[a])
            cols.append(col[b])
            costs.append(offset - w)
    matrix = coo_matrix(
        (costs, (rows, cols)), shape=(len(left), len(right) + len(left))
    ).tocsr()
    a, b = min_weight_full_bipartite_matching(matrix)
    return [(left[i], right[j]) for i, j in zip(a, b) if j < len(right)]


def solve(stream, seconds=30.0):
    global weights, left, right
    nodes = set()
    arcs = []
    for line in map(str.split, stream):
        if not line or line[0] == "c":
            continue
        if line[0] == "p":
            _, kind, n, m = line
        elif line[0] == "n":
            nodes.add(int(line[1]))
        elif line[0] == "a":
            arcs.append(tuple(map(int, line[1:])))
    if kind not in ("bim", "asn") or len(arcs) != int(m):
        raise ValueError("invalid bipartite matching header")
    left = sorted(nodes)
    right = sorted(set(range(1, int(n) + 1)) - nodes)
    weights = {}
    for a, b, *values in arcs:
        if b in nodes:
            a, b = b, a
        if a not in nodes or b in nodes or not 1 <= b <= int(n):
            raise ValueError("invalid bipartite edge")
        weight = values[0] if values and kind == "asn" else 1
        weights[a, b] = max(weights.get((a, b), weight), weight)
    plan = run_pipeline([greedy, optimal], score, initial=[], seconds=seconds)
    return {"solution": plan, "pipeline_score": score(plan)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance",
        type=Path,
        nargs="?",
        default=Path(__file__).with_name("example.txt"),
    )
    parser.add_argument("--seconds", type=float, default=30.0)
    args = parser.parse_args()
    with args.instance.open() as stream:
        print(json.dumps(solve(stream, args.seconds), allow_nan=False))
