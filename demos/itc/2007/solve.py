"""Compare seeded constructions and polish curriculum course room assignments."""
import argparse
from functools import partial
from itertools import combinations
from pathlib import Path
from time import monotonic

from demos.itc.unitime import Plan, score, search
from shiftopt import run_pipeline


def exchange_rooms(path, incumbent, deadline):
    if incumbent is None:
        return None
    data = path.read_text().split("COURSES:\n", 1)[1]
    courses, rest = data.split("ROOMS:\n", 1)
    rooms = rest.split("CURRICULA:", 1)[0]
    sizes = {row[0]: int(row[4]) for row in map(str.split, courses.splitlines()) if row}
    caps = {row[0]: int(row[1]) for row in map(str.split, rooms.splitlines()) if row}
    rows = [line.split() for line in incumbent.text.splitlines()]
    cost = incumbent.cost[0]
    # Exchanging room labels everywhere preserves clashes and the room stability term.
    for a, b in combinations(caps, 2):
        if monotonic() >= deadline:
            break
        swap = {a: b, b: a}
        delta = sum(max(0, sizes[c] - caps[swap[r]]) - max(0, sizes[c] - caps[r])
                    for c, r, _, _ in rows if r in swap)
        if delta < 0:
            for row in rows:
                row[1] = swap.get(row[1], row[1])
            cost += delta
    return Plan((cost,), "".join(" ".join(row) + "\n" for row in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("track", choices=("exam", "tim", "ctt"))
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    steps = [partial(search, args.track, args.input, seed, max(1, args.seconds // 3))
             for seed in (args.seed, args.seed + 1)]
    if args.track == "ctt":
        steps.append(partial(exchange_rooms, args.input))
    plan = run_pipeline(steps, score, seconds=args.seconds)
    if plan is None:
        parser.exit(1, "No schedule accepted within the budget.\n")
    args.output.write_text(plan.text)
    print(*plan.cost)


if __name__ == "__main__":
    main()
