import unittest

from shiftopt import great_deluge, hill_climbing, run_pipeline


class LocalStepTest(unittest.TestCase):
    def test_hill_climbing_crosses_plateau_only_if_enabled(self):
        path = {0: 1, 1: 2}
        costs = [(2,), (2,), (1,)]
        for ties, expected in ((True, 2), (False, 0)):
            step = hill_climbing(lambda x, rng, deadline: path[x], costs.__getitem__,
                                 attempts=2, allow_equal=ties)
            self.assertEqual(run_pipeline([step], costs.__getitem__, initial=0), expected)

    def test_deluge_lowers_ceiling_and_returns_best(self):
        visits = []
        candidates = iter([12, 9, 11, 8])
        def propose(x, rng, deadline):
            visits.append(x)
            return next(candidates)
        step = great_deluge(propose, int, attempts=4, margin=2, target=8)
        self.assertEqual(run_pipeline([step], int, initial=10), 8)
        self.assertEqual(visits, [10, 12, 9, 9])
        self.assertIsNone(run_pipeline([step], int))

    def test_invalid_water_level(self):
        for margin, target in ((-1, 0), (float('nan'), 1), (0, float('inf'))):
            with self.assertRaises(ValueError):
                great_deluge(None, int, attempts=1, margin=margin, target=target)
