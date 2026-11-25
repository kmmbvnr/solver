"""Cycle through search steps after consecutive trials without improvement."""


def stagnation_policy(operators, *, patience=1, prefix=()):
    """Run the prefix once, then keep each operator until patience misses.

    A strict improvement resets the miss count. After the last operator,
    selection wraps to the first. The pipeline owns the deadline and step cap.
    """
    operators, prefix = tuple(operators), tuple(prefix)
    if not operators or len(set(map(id, operators))) != len(operators):
        raise ValueError("supply distinct search operators")
    if type(patience) is not int or patience < 1:
        raise ValueError("patience must be a positive integer")

    def choose(best, history, remaining):
        if len(history) < len(prefix):
            return prefix[len(history)]
        if best is None:
            return None
        trials = len(history) - len(prefix)
        if not trials:
            return operators[0]
        last = history[-1].step
        misses = min(trials, patience)
        if misses == patience and all(
            trial.step is last and not trial.accepted for trial in history[-misses:]
        ):
            index = next(i for i, step in enumerate(operators) if step is last)
            return operators[(index + 1) % len(operators)]
        return last

    return choose
