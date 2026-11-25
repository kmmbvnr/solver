"""Compose optimization steps in an explicit order, retaining the best candidate."""
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from itertools import islice
from math import isfinite
from time import monotonic
from typing import Generic, Protocol, TypeVar

Plan = TypeVar("Plan")


class Heuristic(Protocol[Plan]):
    def __call__(self, incumbent: Plan | None, deadline: float, /) -> Plan | None:
        """Return a feasible proposal without modifying the incumbent, or None."""
        ...


@dataclass(frozen=True)
class StepTrial(Generic[Plan]):
    step: Heuristic[Plan]
    accepted: bool
    elapsed: float
    reward: float = 0.0


class StepPolicy(Protocol[Plan]):
    def __call__(self, best: Plan | None, history: tuple[StepTrial[Plan], ...],
                 remaining: float, /) -> Heuristic[Plan] | None:
        """Choose an available step (possibly again), or None to finish."""


def run_pipeline(steps: Iterable[Heuristic[Plan]], score: Callable, *,
                 initial: Plan | None = None, seconds: float = float("inf"),
                 on_step: Callable | None = None,
                 on_accept: Callable[[Plan], None] | None = None,
                 recombine: Callable[[Plan, Plan, float], Plan | None] | None = None,
                 gain: Callable | None = None,
                 policy: StepPolicy[Plan] | None = None, max_steps: int | None = None) -> Plan | None:
    """Minimize an ordered score. Steps share a cooperative monotonic deadline.

    on_accept(plan) can checkpoint the first proposal and each strict improvement.
    recombine(best, proposal, deadline) can assemble a child before selection.
    The best of both parents and the child survives.
    Policies receive unit reward for improvements unless gain(old, new) is supplied.
    Construction, ties and rejected trials receive zero reward.
    Constructors accept an empty incumbent. A repair step may decline a move.
    on_step(step, old_score, proposed_score, elapsed) observes every completed step.
    """
    if not seconds >= 0:
        raise ValueError("seconds must be nonnegative")
    deadline = monotonic() + seconds
    best = initial
    best_score = None if best is None else score(best)
    if max_steps is not None and (type(max_steps) is not int or max_steps < 0):
        raise ValueError("max_steps must be a nonnegative integer")
    history = []
    if policy is not None:
        if max_steps is None or not isinstance(steps, Sequence):
            raise ValueError("policy selection requires a finite step sequence and max_steps")
        available = tuple(steps)

    def scheduled_steps():
        if policy is None:
            yield from islice(steps, max_steps)
            return
        for _ in range(max_steps):
            remaining = deadline - monotonic()
            if remaining <= 0:
                return
            chosen = policy(best, tuple(history), remaining)
            if chosen is None:
                return
            if not any(chosen is step for step in available):
                raise ValueError("policy chose a step outside the supplied sequence")
            yield chosen

    for step in scheduled_steps():
        started = monotonic()
        if started >= deadline:
            break
        candidate = step(best, deadline)
        previous = best_score
        proposed = None if candidate is None else score(candidate)
        if (recombine is not None and best is not None and candidate is not None
                and candidate is not best and monotonic() < deadline):
            child = recombine(best, candidate, deadline)
            if child is not None:
                child_score = score(child)
                if child_score < proposed:
                    candidate, proposed = child, child_score
        accepted = candidate is not None and (best is None or proposed < best_score)
        reward = 0.
        if policy is not None and accepted and previous is not None:
            reward = 1. if gain is None else float(gain(previous, proposed))
            if not isfinite(reward) or reward < 0:
                raise ValueError("gain must return a finite nonnegative reward")
        if accepted:
            best, best_score = candidate, proposed
            if on_accept is not None:
                on_accept(best)
        elapsed = monotonic() - started
        if policy is not None:
            history.append(StepTrial(step, accepted, elapsed, reward))
        if on_step is not None:
            on_step(step, previous, proposed, elapsed)
    return best
