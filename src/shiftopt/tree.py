"""Restarting best-first tree search with a bounded open list."""
from bisect import insort
from itertools import count
from time import monotonic


def bounded_best_first(root, expand, *, key, priority, complete, score, lower_bound,
                       limits, deadline):
    """Return the best completion found across increasingly wide restarts.

    priority orders open nodes across depths. lower_bound must never exceed
    the score of any descendant. Equal keys must have equivalent continuations
    and attainable scores, including any cost already incurred.
    """
    best = None
    serial = count()
    for capacity in limits:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("frontier limits must be positive")
        if monotonic() >= deadline:
            break
        frontier = [(priority(root), next(serial), root)]
        pending = {key(root)}
        pruned = False
        while frontier and monotonic() < deadline:
            _, _, node = frontier.pop(0)
            pending.remove(key(node))
            if best is not None and lower_bound(node) >= score(best):
                continue
            if complete(node):
                if best is None or score(node) < score(best):
                    best = node
                continue
            for child in expand(node):
                if monotonic() >= deadline:
                    return best
                if complete(child):
                    if best is None or score(child) < score(best):
                        best = child
                    continue
                identity = key(child)
                if identity in pending or (best is not None and lower_bound(child) >= score(best)):
                    continue
                insort(frontier, (priority(child), next(serial), child))
                pending.add(identity)
                if len(frontier) > capacity:
                    pending.remove(key(frontier.pop()[2]))
                    pruned = True
        if not pruned or monotonic() >= deadline:
            break
    return best
