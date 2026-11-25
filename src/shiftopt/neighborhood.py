"""Build a bounded destroy-and-repair step for run_pipeline."""
from random import Random
from time import monotonic


def neighborhood_search(destroy, repair, score, *, attempts, seed=0):
    """Destroy part of the current plan and repair it into a complete proposal.

    destroy(plan, rng) must preserve the input. repair(partial, rng, deadline)
    may return None. The step minimizes score and returns its best complete plan.
    """
    if type(attempts) is not int or attempts < 0:
        raise ValueError("attempts must be a nonnegative integer")

    def search(plan, deadline):
        if plan is None:
            return None
        rng = Random(seed)
        best, best_value = plan, score(plan)
        for _ in range(attempts):
            if monotonic() >= deadline:
                break
            partial = destroy(best, rng)
            if monotonic() >= deadline:
                break
            proposal = repair(partial, rng, deadline)
            if proposal is None:
                continue
            value = score(proposal)
            if value < best_value:
                best, best_value = proposal, value
        return best

    return search
