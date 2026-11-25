"""Search bounded chains of displaced assignments as a pipeline step."""
from time import monotonic

from .neighborhood import neighborhood_search


def ejection_chain(start, extend, close, score, *, max_depth, max_nodes, attempts, seed=0):
    """Return a step that looks for improving complete exchanges.

    start(plan, rng) opens a chain. extend(plan, chain, rng) yields alternatives
    that displace one more assignment. close(plan, chain) proposes a feasible
    complete plan or None. Callbacks must preserve the incumbent and ancestors.
    Each attempt visits at most max_nodes partial chains. The root has depth one.
    """
    if type(max_depth) is not int or max_depth < 1 or type(max_nodes) is not int or max_nodes < 0:
        raise ValueError("max_depth must be positive and max_nodes nonnegative")

    def open_chain(plan, rng):
        return plan, start(plan, rng)

    def search(partial, rng, deadline):
        plan, root = partial
        incumbent = score(plan)
        levels = [iter((root,))]
        visited = 0
        while levels and visited < max_nodes and monotonic() < deadline:
            try:
                chain = next(levels[-1])
            except StopIteration:
                levels.pop()
                continue
            if monotonic() >= deadline:
                break
            visited += 1
            proposal = close(plan, chain)
            if proposal is not None and score(proposal) < incumbent:
                return proposal
            if len(levels) < max_depth and visited < max_nodes and monotonic() < deadline:
                levels.append(iter(extend(plan, chain, rng)))
        return None

    return neighborhood_search(open_chain, search, score, attempts=attempts, seed=seed)
