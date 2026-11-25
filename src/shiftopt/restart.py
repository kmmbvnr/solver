"""Adjust perturbation size from progress between local optima."""


def restart_strength(minimum, maximum):
    """Return a controller that resets on improvement and doubles on stagnation."""
    if type(minimum) is not int or type(maximum) is not int or not 1 <= minimum <= maximum:
        raise ValueError("invalid restart strength range")
    strength = minimum

    def choose(improved):
        nonlocal strength
        strength = minimum if improved else min(maximum, 2 * strength)
        return strength

    return choose
