"""Find a small agreement forest of rooted binary trees."""

import argparse
import json
import re
import sys
from functools import partial
from itertools import combinations
from operator import itemgetter
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def parse(line):
    nodes = []
    stack = []
    for token in re.findall(r"[0-9]+|[)]", line):
        if token == ")":
            b = stack.pop()
            a = stack.pop()
            nodes.append((a, b))
        else:
            nodes.append(int(token))
        stack.append(len(nodes) - 1)
    if len(stack) != 1:
        raise ValueError("invalid binary tree")
    return nodes


def common_clades(plan, deadline, trees, leaves, skip):
    excluded = set(skip)
    intern = {}
    children = {}
    common = None
    for tree in trees:
        ids = []
        for node in tree:
            if isinstance(node, int):
                key = 0 if node in excluded else node
            else:
                a, b = (ids[i] for i in node)
                if not a or not b:
                    key = a or b
                else:
                    pair = tuple(sorted((a, b)))
                    key = intern.setdefault(pair, len(leaves) + len(intern) + 1)
                    children[key] = pair
            ids.append(key)
        common = set(ids) if common is None else common.intersection(ids)
        if monotonic() >= deadline:
            return None
    # Maximal common clades partition the active leaves. Removed leaves stay singletons.
    roots = common - {0}
    nested = {c for key in roots if key in children for c in children[key]}
    result = [f"{v};" for v in sorted(excluded)]
    for root in sorted(roots - nested):
        tokens = []
        stack = [";", root]
        while stack:
            v = stack.pop()
            if v in children:
                a, b = children[v]
                stack.extend([")", b, ",", a, "("])
            else:
                tokens.append(str(v))
        result.append("".join(tokens))
    return len(result), result


def solve(stream, seconds):
    trees = [
        parse(line) for line in stream if line.strip() and not line.startswith("#")
    ]
    leaves = sorted(v for v in trees[0] if isinstance(v, int))
    initial = (len(leaves), [f"{v};" for v in leaves])
    skips = [
        (),
        *[(v,) for v in leaves[:16]],
        *combinations(leaves[:12], 2),
        *combinations(leaves[:8], 3),
        leaves[::2],
        leaves[1::2],
    ]
    steps = [partial(common_clades, trees=trees, leaves=leaves, skip=s) for s in skips]
    return run_pipeline(steps, itemgetter(0), initial=initial, seconds=seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "instance", nargs="?", default=str(Path(__file__).with_name("example.txt"))
    )
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument(
        "--json",
        action="store_true",
        help="include the objective in machine-readable output",
    )
    args = parser.parse_args()
    if args.instance == "-":
        value, lines = solve(sys.stdin, args.seconds)
    else:
        with open(args.instance) as stream:
            value, lines = solve(stream, args.seconds)
    if args.json:
        print(json.dumps({"objective": value, "solution": lines}, allow_nan=False))
    else:
        sys.stdout.writelines(str(line) + "\n" for line in lines)
