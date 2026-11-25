"""Select pipeline operators using observed rewards and an exploration bonus."""
from math import isfinite, log1p, sqrt


def bandit_policy(operators, *, construct=None, exploration=1.0):
    """Try each operator, then maximize its mean reward plus a UCB bonus."""
    operators = tuple(operators)
    index = {id(op): i for i, op in enumerate(operators)}
    if not operators or len(index) != len(operators):
        raise ValueError("supply distinct operators")
    if not isfinite(exploration) or exploration < 0:
        raise ValueError("exploration must be finite and nonnegative")

    def choose(best, history, remaining):
        if best is None and construct is not None:
            return construct if not history else None
        counts = [0] * len(operators)
        rewards = [0.] * len(operators)
        for trial in history:
            i = index.get(id(trial.step))
            if i is not None:
                counts[i] += 1
                rewards[i] += trial.reward
        if 0 in counts:
            return operators[counts.index(0)]
        log_total = log1p(sum(counts))
        def priority(i):
            return rewards[i] / counts[i] + exploration * sqrt(log_total / counts[i])
        return operators[max(range(len(operators)), key=priority)]

    return choose
