"""Bounded search over successive decisions."""

from heapq import nsmallest
from time import monotonic


def beam_search(initial, expand, *, key, priority, complete, width, deadline):
    """Expand one decision per layer and keep the best state for each key.

    Return the lowest-priority complete state on the first retained layer
    containing one, or None on exhaustion or timeout. Expansion shares the
    caller's monotonic deadline and is checked between states.
    """
    if width < 1:
        raise ValueError("width must be positive")
    frontier = [initial]
    while frontier:
        finished = [s for s in frontier if complete(s)]
        if finished:
            return min(finished, key=priority)
        candidates = {}
        for state in frontier:
            if monotonic() >= deadline:
                return None
            for child in expand(state):
                identity = key(child)
                if identity not in candidates or priority(child) < priority(candidates[identity]):
                    candidates[identity] = child
        frontier = nsmallest(width, candidates.values(), key=priority)
    return None
