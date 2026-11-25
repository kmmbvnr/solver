"""Build a bounded destroy-and-repair step for run_pipeline."""
from functools import partial
from math import exp, isfinite
from random import Random
from time import monotonic


_EXPIRED = object()


def neighborhood_search(destroy, repair, score, *, attempts, seed=0, temperature=0.0):
    """Destroy part of the current plan and repair it into a complete proposal.

    destroy(plan, rng) must preserve the input. repair(partial, rng, deadline)
    may return None. The step minimizes score and returns its best complete plan.
    A positive temperature enables Metropolis acceptance for numeric scores.
    It cools exponentially with the attempt count. The returned plan is the best seen.
    """
    move = partial(_repair_move, destroy, repair)
    return _search_step(move, score, attempts, seed, temperature)


def _repair_move(destroy, repair, current, rng, deadline):
    partial_plan = destroy(current, rng)
    if monotonic() >= deadline:
        return _EXPIRED
    return repair(partial_plan, rng, deadline)


def simulated_annealing(move, score, *, attempts, temperature, seed=0):
    """Return a pipeline step for numeric minimization with exponential cooling.

    move(current, rng, deadline) returns a feasible neighbor or None and
    preserves current. The step returns the best plan visited.
    """
    if temperature <= 0:
        raise ValueError("annealing requires a positive temperature")
    return _search_step(move, score, attempts, seed, temperature)


def _search_step(move, score, attempts, seed, temperature):
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
            proposal = move(current, rng, deadline)
            if proposal is _EXPIRED:
                break
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
