"""Compose optimization steps in an explicit order, retaining the best candidate."""
from collections.abc import Callable, Iterable
from time import monotonic
from typing import Protocol, TypeVar

Plan = TypeVar("Plan")


class Heuristic(Protocol[Plan]):
    def __call__(self, incumbent: Plan | None, deadline: float, /) -> Plan | None:
        """Return a feasible proposal without modifying the incumbent, or None."""
        ...


def run_pipeline(steps: Iterable[Heuristic[Plan]], score: Callable, *,
                 initial: Plan | None = None, seconds: float = float("inf"),
                 on_step: Callable | None = None) -> Plan | None:
    """Minimize an ordered score. Steps share a cooperative monotonic deadline.

    Constructors accept an empty incumbent. A repair step may decline a move.
    on_step(step, old_score, proposed_score, elapsed) observes every completed step.
    """
    if not seconds >= 0:
        raise ValueError("seconds must be nonnegative")
    deadline = monotonic() + seconds
    best = initial
    best_score = None if best is None else score(best)
    for step in steps:
        started = monotonic()
        if started >= deadline:
            break
        candidate = step(best, deadline)
        previous = best_score
        proposed = None if candidate is None else score(candidate)
        if candidate is not None and (best is None or proposed < best_score):
            best, best_score = candidate, proposed
        if on_step is not None:
            on_step(step, previous, proposed, monotonic() - started)
    return best
