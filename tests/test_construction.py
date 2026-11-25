import unittest
from math import inf
from shiftopt import assignment_constructor, run_pipeline


class Bins:
    """Assign three items to distinct eligible bins."""
    allowed = ((0, 1), (0,), (1, 2))

    def __init__(self):
        self.bins = {}

    def options(self, item, rng):
        for choice in self.allowed[item]:
            yield choice, sum(1 << i for i, b in self.bins.items() if b == choice)

    def remove(self, item):
        del self.bins[item]

    def assign(self, item, choice):
        self.bins[item] = choice

    def finish(self):
        return tuple(self.bins[i] for i in range(3))


def empty_bins(rng):
    return Bins(), [0, 2, 1]


class ConstructorTests(unittest.TestCase):
    def test_memory_breaks_repeated_evictions_and_resets_between_calls(self):
        for weight, expected in ((0, None), (1, (1, 0, 2))):
            step = assignment_constructor(empty_bins, moves_per_start=12, conflict_weight=weight)
            for _ in range(2):
                self.assertEqual(run_pipeline([step], tuple), expected)

    def test_failed_reconstruction_preserves_incumbent(self):
        step = assignment_constructor(empty_bins, moves_per_start=1, starts=2)
        plan = (1, 0, 2)
        self.assertIs(plan, run_pipeline([step], tuple, initial=plan))
        self.assertIsNone(step(None, 0))

    def test_unlimited_restarts_need_deadline(self):
        step = assignment_constructor(empty_bins, moves_per_start=12, starts=None)
        with self.assertRaises(ValueError):
            step(None, inf)
