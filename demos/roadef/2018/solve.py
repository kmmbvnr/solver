"""Select ordered stack prefixes that fit in a guillotine strip."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from time import monotonic

import numpy as np
from shiftopt import run_pipeline, select_candidates


def records(path):
    with path.open(encoding="utf-8-sig") as stream:
        yield from csv.reader(stream, delimiter=";")


def pack(stacks, width, height, trim, min_row):
    candidates, values, heights, owners = [], [], [], []
    for group, (key, items) in enumerate(stacks.items()):
        prefix = []
        used = area = 0
        for _, item, a, b in items:
            orientations = [(h, w) for w, h in ((a, b), (b, a))
                            if w == width or (w <= width-trim and h >= min_row)]
            if not orientations:
                break
            h, w = min(orientations)
            used += h
            if used > height:
                break
            prefix.append((item, w, h))
            area += w*h
            candidates.append((key, tuple(prefix)))
            values.append(area)
            heights.append(used)
            owners.append(group)
    if not candidates:
        return []
    usage = np.zeros((1+len(stacks), len(values)))
    usage[0] = heights
    usage[1+np.array(owners), np.arange(len(values))] = 1
    choice = select_candidates(values, usage, [height]+[1]*len(stacks), time_limit=0.04)
    return [candidates[i] for i in choice.selected]


def read_problem(folder, name, params):
    settings = {k: int(v) for k, v in list(records(params))[1:]}
    stacks = defaultdict(list)
    for row in list(records(folder/f"{name}_batch.csv"))[1:]:
        item, w, h, key, seq = map(int, row)
        stacks[key].append((seq, item, w, h))
    for items in stacks.values():
        items.sort()
    defects = defaultdict(list)
    for row in list(records(folder/f"{name}_defects.csv"))[1:]:
        _, plate, x, y, w, h = (int(float(v)) for v in row)
        defects[plate].append((x, y, x+w, y+h))
    return settings, dict(stacks), defects


def strips(problem, deadline):
    settings, original, defects = problem
    W, H = settings["widthPlates"], settings["heightPlates"]
    trim = settings["minWaste"]
    stacks = {key: list(items) for key, items in original.items()}
    nodes = []

    def node(x, y, w, h, kind, depth, parent):
        idx = len(nodes)
        nodes.append((plate, idx, x, y, w, h, kind, depth, parent))
        return idx

    for plate in range(settings["nPlates"]):
        root = node(0, 0, W, H, -2, 0, "")
        x = 0
        while stacks and W-x >= settings["min1Cut"]:
            if monotonic() >= deadline:
                return None
            widths = sorted({v for items in stacks.values() for v in items[0][2:]
                             if settings["min1Cut"] <= v <= min(W-x, settings["max1Cut"])})
            if len(widths) > 4:
                widths = [widths[i*(len(widths)-1)//3] for i in range(4)]
            best = None
            for width in widths:
                right = x+width
                if 0 < W-right < trim or any(dx < right < dr for dx, _, dr, _ in defects[plate]):
                    continue
                # Reserve full-width waste bands around defects. Every cut inside a
                # free band is then clear across the entire strip.
                obstacles = sorted((max(0, y-trim), min(H, top+trim))
                                   for dx, y, dr, top in defects[plate] if dx < right and x < dr)
                bands = []
                low = 0
                for start, end in obstacles + [(H, H)]:
                    if start-low > trim:
                        bands.append((low, start))
                    low = max(low, end)
                # Width trials share the same stack heads. Evaluate the largest
                # clear band and let the solver choose compatible prefixes.
                if not bands:
                    continue
                low, high = max(bands, key=lambda b: b[1]-b[0])
                if 0 < low < trim:
                    low = trim
                groups = pack(stacks, width, high-low-trim, trim, settings["min2Cut"])
                area = sum(w*h for _, items in groups for _, w, h in items)
                if area and (best is None or area/width > best[0]):
                    best = area/width, width, low, groups
            if best is None:
                break
            _, width, y, groups = best
            strip = node(x, 0, width, H, -2, 1, root)
            if y:
                node(x, 0, width, y, -1, 2, strip)
            for key, items in groups:
                for item, w, h in items:
                    row = node(x, y, width, h, item if w == width else -2, 2, strip)
                    if w != width:
                        node(x, y, w, h, item, 3, row)
                        node(x+w, y, width-w, h, -1, 3, row)
                    y += h
                del stacks[key][:len(items)]
                if not stacks[key]:
                    del stacks[key]
            node(x, y, width, H-y, -1, 2, strip)
            x += width
        if x < W:
            node(x, 0, W-x, H, -1 if stacks else -3, 1, root)
        if not stacks:
            break
    if stacks:
        return None
    return nodes


def write_plan(nodes, output):
    with output.open("w", newline="") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\n")
        writer.writerow("PLATE_ID NODE_ID X Y WIDTH HEIGHT TYPE CUT PARENT".split())
        writer.writerows(nodes)


def solve(folder, name, params, output, stages=("strips", "shelves", "repair", "beam", "imba"), seconds=170, on_step=None):
    from beam import beam_plan
    from shelves import build_shelves

    problem = read_problem(folder, name, params)
    settings = problem[0]
    def used_width(nodes):
        last_plate = nodes[-1][0]
        residual = nodes[-1][4] if nodes[-1][6] == -3 else 0
        return (last_plate + 1) * settings["widthPlates"] - residual

    def baseline(plan, deadline):
        return strips(problem, deadline)

    def shelves(plan, deadline):
        return build_shelves(problem, deadline)

    def repair(plan, deadline):
        if plan is None:
            return None
        # Reopen the last four plates. Their old cuts can be replaced together.
        first = max(0, plan[-1][0] - 3)
        prefix = [row for row in plan if row[0] < first]
        return build_shelves(problem, deadline, prefix=prefix, fine=True)

    def beam(plan, deadline):
        best = plan
        for breadth in (12, 48, 128):
            candidate = beam_plan(problem, deadline, breadth)
            if candidate is None:
                break
            if best is None or used_width(candidate) < used_width(best):
                best = candidate
        return best

    def imba(plan, deadline):
        return beam_plan(problem, deadline)

    operators = {"imba": imba, "strips": baseline, "shelves": shelves, "repair": repair, "beam": beam}
    result = run_pipeline([operators[s] for s in stages], used_width, seconds=seconds, on_step=on_step)
    if result is None:
        raise ValueError("No complete cutting plan found within the budget")
    write_plan(result, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("instance")
    parser.add_argument("output", type=Path)
    parser.add_argument("--stages", nargs="+", choices=("strips", "shelves", "repair", "beam", "imba"),
                        default=("strips", "shelves", "repair", "beam", "imba"))
    parser.add_argument("--seconds", type=float, default=170)
    args = parser.parse_args()
    solve(args.folder, args.instance, Path(__file__).parent/"data/global_param.csv", args.output, args.stages, args.seconds)
