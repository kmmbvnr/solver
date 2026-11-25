"""Build set covers by lazily updating marginal coverage gains."""

from heapq import heapify, heappop, heappush
from time import monotonic


def greedy_cover(plan, deadline, *, sets, universe, reverse=False):
    """Choose integer candidate IDs covering the universe, or return None on timeout."""
    remaining = set(universe)
    chosen = []
    heap = [(-len(s), -v if reverse else v, v) for v, s in sets.items()]
    heapify(heap)
    while remaining:
        if monotonic() >= deadline:
            return None
        if not heap:
            raise ValueError("uncoverable instance")
        bound, tie, v = heappop(heap)
        gain = sets[v] & remaining
        if not gain:
            continue
        if len(gain) < -bound:
            heappush(heap, (-len(gain), tie, v))
        else:
            chosen.append(v)
            remaining -= gain
    return chosen
