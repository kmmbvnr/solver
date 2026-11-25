"""Search item placements, allowing the current strip to grow with each row."""

from typing import NamedTuple
from shiftopt import beam_search
from shiftopt.tree import bounded_best_first


class State(NamedTuple):
    positions: tuple
    plate: int
    x: int
    width: int
    y: int
    height: int
    filled: int
    area: int
    count: int
    cost: float
    parent: object
    placement: tuple


def clear_row(defects, x, width, old_width, bottom, filled, height, trim):
    """Find a clear row without moving items already placed in this strip."""
    y = bottom
    for dx, dy, right, top in defects:
        if dx < x + width < right:
            return None
        if right <= x or dx >= x + width:
            continue
        if old_width and width > old_width and right > x + old_width and dy < bottom:
            return None
        if y < top and dy < y + height:
            if filled:
                return None
            y = max(top, bottom + trim)
    # Moving above one defect can bring the row into another.
    if any(
        dx < x + width and x < right and dy < y + height and y < top
        for dx, dy, right, top in defects
    ):
        return None
    return y


def beam_plan(problem, deadline, breadth=None):
    settings, stacks, defects = problem
    W, H = settings["widthPlates"], settings["heightPlates"]
    trim, max_width = settings["minWaste"], settings["max1Cut"]
    stacks = list(stacks.values())
    total = sum(map(len, stacks))
    initial = State((0,) * len(stacks), 0, 0, 0, 0, 0, 0, 0, 0, 0, None, ())

    def expand(s):
        # Append to the current row, open a row, open a strip, or open a plate.
        starts = []
        if s.count:
            starts.append((s.plate, s.x, s.y, s.filled, s.height, s.width))
            starts.append((s.plate, s.x, s.y + s.height, 0, 0, s.width))
            starts.append((s.plate, s.x + s.width, 0, 0, 0, 0))
        if not s.count or s.plate + 1 < settings["nPlates"]:
            starts.append((s.plate + bool(s.count), 0, 0, 0, 0, 0))
        for plate, x, bottom, left, old_h, old_w in starts:
            if W - x < settings["min1Cut"] or H - bottom < settings["min2Cut"]:
                continue
            seen = set()
            for stack, pos in enumerate(s.positions):
                if pos == len(stacks[stack]):
                    continue
                _, item, a, b = stacks[stack][pos]
                # Terminal items of identical size are interchangeable.
                if pos + 1 == len(stacks[stack]):
                    size = (min(a, b), max(a, b))
                    if size in seen:
                        continue
                    seen.add(size)
                for w, h in ((a, b), (b, a)):
                    height = old_h or h
                    if h > height or 0 < height - h < trim or height < settings["min2Cut"]:
                        continue
                    end = left + w
                    width = max(old_w, end, settings["min1Cut"])
                    if 0 < width - end < trim or (old_w and 0 < width - old_w < trim):
                        width = max(old_w, end) + trim
                    if width > max_width or x + width > W or 0 < W - x - width < trim:
                        continue
                    y = clear_row(defects[plate], x, width, old_w, bottom, left, height, trim)
                    if y is None or y + height > H or 0 < H - y - height < trim:
                        continue
                    area = s.area + w * h
                    count = s.count + 1
                    consumed = (plate * W + x) * H + width * y + end * height
                    if count == total:
                        cost = (plate * W + x + width) * H
                    else:
                        # Project waste density, charging partly for open space.
                        exposed = (width - end) * height + width * (H - y - height)
                        cost = (consumed - area + 0.10 * exposed) / area
                    positions = s.positions[:stack] + (pos + 1,) + s.positions[stack + 1 :]
                    yield State(
                        positions,
                        plate,
                        x,
                        width,
                        y,
                        height,
                        end,
                        area,
                        count,
                        cost,
                        s,
                        (plate, x, y, left, item, w, h),
                    )

    if breadth is None:
        state = bounded_best_first(initial, expand, key=lambda s: s[:7], priority=lambda s: s.cost,
                                   complete=lambda s: s.count == total, score=lambda s: s.cost,
                                   lower_bound=lambda s: (s.plate * W + s.x + s.width) * H,
                                   limits=(1, 4, 16, 64, 256), deadline=deadline)
        return None if state is None else cutting_tree(state, W, H)

    state = beam_search(
        initial,
        expand,
        key=lambda s: s[:7],
        priority=lambda s: s.cost,
        complete=lambda s: s.count == total,
        width=breadth,
        deadline=deadline,
    )
    return None if state is None else cutting_tree(state, W, H)


def cutting_tree(state, plate_width, plate_height):
    """Recover cut dimensions after the last expansion of each strip."""
    W, H = plate_width, plate_height
    plates = {}
    while state.parent is not None:
        plate, x, y, left, item, w, h = state.placement
        strips = plates.setdefault(plate, {})
        _, rows = strips.setdefault(x, (state.width, {}))
        rows.setdefault(y, []).append((left, item, w, h))
        state = state.parent
    nodes = []

    def add(x, y, w, h, kind, cut, parent):
        idx = len(nodes)
        nodes.append((plate, idx, x, y, w, h, kind, cut, parent))
        return idx

    for plate in sorted(plates):
        root = add(0, 0, W, H, -2, 0, "")
        for x, (width, rows) in sorted(plates[plate].items()):
            strip = add(x, 0, width, H, -2, 1, root)
            low = 0
            for y, items in sorted(rows.items()):
                items.reverse()
                height = items[0][3]
                if y > low:
                    add(x, low, width, y - low, -1, 2, strip)
                if items[0][2] == width:
                    add(x, y, width, height, items[0][1], 2, strip)
                else:
                    row = add(x, y, width, height, -2, 2, strip)
                    for left, item, w, h in items:
                        if h == height:
                            add(x + left, y, w, h, item, 3, row)
                        else:
                            cell = add(x + left, y, w, height, -2, 3, row)
                            add(x + left, y, w, h, item, 4, cell)
                            add(x + left, y + h, w, height - h, -1, 4, cell)
                    end = left + w
                    if end < width:
                        add(x + end, y, width - end, height, -1, 3, row)
                low = y + height
            if low < H:
                add(x, low, width, H - low, -1, 2, strip)
        if x + width < W:
            add(x + width, 0, W - x - width, H, -3 if plate == max(plates) else -1, 1, root)
    return nodes
