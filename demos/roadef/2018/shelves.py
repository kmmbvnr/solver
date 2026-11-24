"""Construct horizontal rows with several items and rebuild a suffix of plates."""
from time import monotonic


def clear_bands(defects, x, width, height, trim):
    blocked = sorted((max(0, y-trim), min(height, top+trim))
                     for left, y, right, top in defects if left < x+width and x < right)
    low = 0
    for start, end in blocked + [(height, height)]:
        if start > low:
            yield low, start
        low = max(low, end)


def fill_strip(stacks, positions, width, bands, trim, min_height):
    positions = positions.copy()
    rows = []
    area = 0
    for y, top in bands:
        while top-y >= min_height:
            room = width
            row_height = 0
            items = []
            while room >= trim:
                best = None
                for key, stack in stacks.items():
                    pos = positions[key]
                    if pos == len(stack):
                        continue
                    _, item, a, b = stack[pos]
                    for w, h in ((a, b), (b, a)):
                        if w > room or 0 < room-w < trim:
                            continue
                        if row_height:
                            if h > row_height or 0 < row_height-h < trim:
                                continue
                            priority = (h, w)
                        else:
                            if h < min_height or h > top-y or 0 < top-y-h < trim:
                                continue
                            priority = (w*h, w)
                        candidate = (priority, key, item, w, h)
                        if best is None or candidate > best:
                            best = candidate
                if best is None:
                    break
                _, key, item, w, h = best
                positions[key] += 1
                items.append((item, w, h))
                room -= w
                row_height = row_height or h
                area += w*h
            if not items:
                break
            rows.append((y, row_height, items))
            y += row_height
    return area, positions, rows


def build_shelves(problem, deadline, *, prefix=(), fine=False):
    settings, stacks, defects = problem
    W, H = settings["widthPlates"], settings["heightPlates"]
    trim = settings["minWaste"]
    nodes = list(prefix)
    finished = {n[6] for n in prefix if n[6] >= 0}
    positions = {key: sum(item in finished for _, item, _, _ in stack)
                 for key, stack in stacks.items()}
    remaining = sum(map(len, stacks.values())) - len(finished)

    def add(x, y, w, h, kind, depth, parent):
        idx = len(nodes)
        nodes.append((plate, idx, x, y, w, h, kind, depth, parent))
        return idx

    for plate in range(prefix[-1][0]+1 if prefix else 0, settings["nPlates"]):
        root = add(0, 0, W, H, -2, 0, "")
        x = 0
        while remaining and W-x >= settings["min1Cut"]:
            if monotonic() >= deadline:
                return None
            max_width = min(settings["max1Cut"], W-x)
            widths = sorted({v for k, stack in stacks.items() if positions[k] < len(stack)
                             for v in stack[positions[k]][2:] if settings["min1Cut"] <= v <= max_width})
            count = 12 if fine else 5
            if len(widths) > count:
                widths = [widths[i*(len(widths)-1)//(count-1)] for i in range(count)]
            widths = sorted(set(widths + [max_width, (W-x)//2]))
            best = None
            for width in widths:
                if not settings["min1Cut"] <= width <= max_width or 0 < W-x-width < trim:
                    continue
                if any(left < x+width < right for left, _, right, _ in defects[plate]):
                    continue
                bands = clear_bands(defects[plate], x, width, H, trim)
                area, after, rows = fill_strip(stacks, positions, width, bands, trim, settings["min2Cut"])
                if area and (best is None or area/width > best[0]):
                    best = area/width, width, after, rows
            if best is None:
                break
            _, width, positions, rows = best
            strip = add(x, 0, width, H, -2, 1, root)
            low = 0
            for y, height, items in rows:
                if y > low:
                    add(x, low, width, y-low, -1, 2, strip)
                first, w, h = items[0]
                if w == width:
                    add(x, y, w, h, first, 2, strip)
                else:
                    row = add(x, y, width, height, -2, 2, strip)
                    left = x
                    for item, w, h in items:
                        if h == height:
                            add(left, y, w, h, item, 3, row)
                        else:
                            cell = add(left, y, w, height, -2, 3, row)
                            add(left, y, w, h, item, 4, cell)
                            add(left, y+h, w, height-h, -1, 4, cell)
                        left += w
                    if left < x+width:
                        add(left, y, x+width-left, height, -1, 3, row)
                remaining -= len(items)
                low = y+height
            if low < H:
                add(x, low, width, H-low, -1, 2, strip)
            x += width
        if x < W:
            add(x, 0, W-x, H, -1 if remaining else -3, 1, root)
        if not remaining:
            return nodes
    return None
