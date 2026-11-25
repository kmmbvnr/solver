import unittest
from unittest.mock import patch

from shiftopt import neighborhood_search, run_pipeline


class NeighborhoodTests(unittest.TestCase):
    def test_repair_may_decline_and_ordered_scores_work_with_strict_acceptance(self):
        visits = []
        proposals = iter([None, (4, 2), (5, 0), (4, 1)])

        def destroy(plan, rng):
            visits.append(plan)
            return plan

        step = neighborhood_search(destroy, lambda part, rng, end: next(proposals),
                                   tuple, attempts=4)
        self.assertEqual(run_pipeline([step], tuple, initial=(6, 0)), (4, 1))
        self.assertEqual(visits, [(6, 0), (6, 0), (4, 2), (4, 2)])

    def test_metropolis_can_cross_a_barrier_and_keeps_the_best(self):
        def trial(plan, rng, deadline):
            return {3: 4, 4: 1, 1: 9}[plan]

        for temperature, expected in [(0, 3), (1e8, 1)]:
            step = neighborhood_search(lambda plan, rng: plan, trial, int, attempts=3,
                                       seed=7, temperature=temperature)
            self.assertEqual(run_pipeline([step], int, initial=3), expected)

    def test_deadline_between_destroy_and_repair(self):
        def repair(*args):
            self.fail("repair started after deadline")

        step = neighborhood_search(lambda plan, rng: plan, repair, int, attempts=2)
        with patch("shiftopt.neighborhood.monotonic", side_effect=[0, 2]):
            self.assertEqual(step(7, 1), 7)

    def test_invalid_controls(self):
        for settings in [dict(attempts=-1), dict(attempts=1, temperature=float("nan"))]:
            with self.assertRaises(ValueError):
                neighborhood_search(None, None, int, **settings)
