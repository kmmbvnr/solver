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
    return _temperature_step(move, score, attempts, seed, temperature)


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
    return _temperature_step(move, score, attempts, seed, temperature)


def hill_climbing(move, score, *, attempts, seed=0, allow_equal=True):
    """Sample one feasible neighbor per attempt. Equal scores may cross plateaus."""
    return _search_step(move, score, attempts, seed, _plateau if allow_equal else _strict)


def great_deluge(move, score, *, attempts, margin, target, seed=0):
    """Accept improving moves or numeric costs below a falling water level.

    The level falls linearly from starting cost + margin to target. A target
    above the starting cost is clamped to that cost. The best visited plan survives.
    """
    if not isfinite(margin) or margin < 0 or not isfinite(target):
        raise ValueError("margin must be finite and nonnegative and target finite")
    return _search_step(move, score, attempts, seed, partial(_below_level, margin, target))


def _strict(initial, current, value, i, attempts, rng):
    return False


def _plateau(initial, current, value, i, attempts, rng):
    return value == current


def _below_level(margin, target, initial, current, value, i, attempts, rng):
    start = initial + margin
    end = min(initial, target)
    fraction = i / max(1, attempts - 1)
    return value <= start + (end - start) * fraction


def _metropolis(temperature, initial, current, value, i, attempts, rng):
    scale = temperature * exp(-4 * i / attempts)
    return scale > 0 and rng.random() < exp((current - value) / scale)


def _temperature_step(move, score, attempts, seed, temperature):
    if not isfinite(temperature) or temperature < 0:
        raise ValueError("temperature must be finite and nonnegative")
    accept = partial(_metropolis, temperature) if temperature else _strict
    return _search_step(move, score, attempts, seed, accept)


def _search_step(move, score, attempts, seed, accept):
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
        initial_value = current_value = best_value = score(plan)
        for i in range(attempts):
            if monotonic() >= deadline:
                break
            proposal = move(current, rng, deadline)
            if proposal is _EXPIRED:
                break
            if proposal is None:
                continue
            value = score(proposal)
            if value < current_value or accept(initial_value, current_value, value, i, attempts, acceptance):
                current, current_value = proposal, value
            if value < best_value:
                best, best_value = proposal, value
        return best

    return search


class ResumableAnnealing:
    """One run's annealing trajectory, yielding its best plan after each burst.

    A cycle cools over cycle_attempts proposals, then restarts at the best plan
    with the next seed. A better external incumbent replaces the current point
    without resetting the cooling schedule. Create a fresh step per run.
    """

    def __init__(self, move, score, *, attempts, cycle_attempts, temperature, seed=0):
        if any(type(n) is not int or n < 1 for n in (attempts, cycle_attempts)):
            raise ValueError("attempt budgets must be positive integers")
        if not isfinite(temperature) or temperature <= 0 or not isinstance(seed, int):
            raise ValueError("supply a positive finite temperature and an integer seed")
        self.move, self.score = move, score
        self.attempts, self.cycle_attempts = attempts, cycle_attempts
        self.temperature, self.seed = temperature, seed
        self.position = 0
        self.best = self.current = None

    def __call__(self, incumbent, deadline):
        if incumbent is None:
            return None
        value = self.score(incumbent)
        if self.best is None or value < self.best_value:
            self.best = self.current = incumbent
            self.best_value = self.current_value = value
        for _ in range(self.attempts):
            if monotonic() >= deadline:
                break
            if self.position == 0:
                self.rng = Random(self.seed)
                self.acceptance = Random(self.seed ^ 0xAF17)
                self.seed += 1
                self.current, self.current_value = self.best, self.best_value
            proposal = self.move(self.current, self.rng, deadline)
            i = self.position
            self.position = (i + 1) % self.cycle_attempts
            if proposal is None:
                continue
            value = self.score(proposal)
            if value < self.current_value or _metropolis(
                self.temperature, self.best_value, self.current_value, value, i,
                self.cycle_attempts, self.acceptance,
            ):
                self.current, self.current_value = proposal, value
            if value < self.best_value:
                self.best, self.best_value = proposal, value
        return self.best
