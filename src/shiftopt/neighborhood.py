"""Build a bounded destroy-and-repair step for run_pipeline."""
from math import exp, isfinite
from random import Random
from time import monotonic


def neighborhood_search(destroy, repair, score, *, attempts, seed=0, temperature=0.0):
    """Destroy part of the current plan and repair it into a complete proposal.

    destroy(plan, rng) must preserve the input. repair(partial, rng, deadline)
    may return None. The step minimizes score and returns its best complete plan.
    A positive temperature enables Metropolis acceptance for numeric scores.
    It cools exponentially with the attempt count. The returned plan is the best seen.
    """
    if not isfinite(temperature) or temperature < 0:
        raise ValueError("temperature must be finite and nonnegative")
    if not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if type(attempts) is not int or attempts < 0:
        raise ValueError("attempts must be a nonnegative integer")

    def search(plan, deadline):
        if plan is None:
            return None
        rng = Random(seed)
        acceptance = Random(seed ^ 0xAF17)
        current = best = plan
        current_value = best_value = score(plan)
        for i in range(attempts):
            if monotonic() >= deadline:
                break
            partial = destroy(current, rng)
            if monotonic() >= deadline:
                break
            proposal = repair(partial, rng, deadline)
            if proposal is None:
                continue
            value = score(proposal)
            if value < current_value:
                current, current_value = proposal, value
            elif temperature > 0:
                scale = temperature * exp(-4 * i / attempts)
                if scale and acceptance.random() < exp((current_value - value) / scale):
                    current, current_value = proposal, value
            if value < best_value:
                best, best_value = proposal, value
        return best

    return search
