"""Search for a longest undirected path or a maximum-weight directed k-path."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path
from time import monotonic

from shiftopt import run_pipeline


def explore(plan, deadline, graph, k, weighted, reverse):
    best = plan
    starts = sorted(graph, key=lambda v: (len(graph[v]), v), reverse=reverse)
    exhausted = True
    for i, start in enumerate(starts):
        # Divide the remaining time across starts so a dense component cannot monopolize it.
        now = monotonic()
        until = now + (deadline - now) / (len(starts) - i)
        stack = [(start, (start,), 0)]
        while stack and monotonic() < until:
            v, path, weight = stack.pop()
            length = len(path) - 1
            if not weighted or length == k:
                score = weight if weighted else length
                if best is None or score > best[0]:
                    best = (score, path)
                if length == (k if weighted else len(graph) - 1):
                    if not weighted:
                        return best
                    continue
            options = sorted(
                (w, -len(graph[u]), u) for u, w in graph[v] if u not in path
            )
            for w, _, u in options:
                stack.append((u, (*path, u), weight + w))
        exhausted = exhausted and not stack
        if monotonic() >= deadline:
            exhausted = exhausted and i + 1 == len(starts)
            break
    if weighted and best is None and exhausted:
        return (0, ())
    return best


def maximize(plan):
    return -plan[0]


def solve(stream, seconds):
    rows = (
        line.split() for line in stream if line.strip() and not line.startswith("c")
    )
    _, tag, n, m, *target = next(rows)
    weighted = tag == "digraph"
    graph = {v: [] for v in range(1, int(n) + 1)}
    for _, a, b, *weight in rows:
        u, v = int(a), int(b)
        graph[u].append((v, int(weight[0]) if weighted else 1))
        if not weighted:
            graph[v].append((u, 1))
    k = int(target[0]) if weighted else len(graph) - 1
    initial = None if weighted else (0, (next(iter(graph)),))
    steps = [
        partial(explore, graph=graph, k=k, weighted=weighted, reverse=r)
        for r in (False, True)
    ]
    result = run_pipeline(steps, maximize, initial=initial, seconds=seconds)
    if result is None:
        raise ValueError("no path of the requested length found within budget")
    score, path = result
    if not path:
        return 0, ["0 0"]
    return score, [f"{k} {score}" if weighted else score, *path]


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
