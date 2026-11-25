import unittest

from shiftopt import run_pipeline, simulated_annealing


def cross_barrier(value, rng, deadline):
    return {2: 3, 3: 0, 0: 4}[value]


class AnnealingTest(unittest.TestCase):
    def test_crosses_uphill_barrier_and_keeps_best(self):
        step = simulated_annealing(cross_barrier, int, attempts=3,
                                   temperature=100, seed=0)
        self.assertEqual(run_pipeline([step], int, initial=2), 0)
        self.assertIsNone(run_pipeline([step], int))
