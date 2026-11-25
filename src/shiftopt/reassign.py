"""Build a local reassignment step from candidate transfers and a feasibility check."""
from time import monotonic


def reassignment_search(transfers, rebuild, score, *, attempts):
    """Rebuild affected assignments on the current best plan and compare full costs.

    transfers(initial_plan) yields move descriptors. rebuild(plan, move, deadline)
    returns a complete feasible plan or None if the move is stale or infeasible.
    """
    if type(attempts) is not int or attempts < 0:
        raise ValueError("attempts must be a nonnegative integer")

    def search(plan, deadline):
        if plan is None or not attempts or monotonic() >= deadline:
            return plan
        value = score(plan)
        moves = iter(transfers(plan))
        for _ in range(attempts):
            if monotonic() >= deadline:
                break
            try:
                move = next(moves)
            except StopIteration:
                break
            if monotonic() >= deadline:
                break
            proposal = rebuild(plan, move, deadline)
            if proposal is not None:
                cost = score(proposal)
                if cost < value:
                    plan, value = proposal, cost
        return plan
    return search
