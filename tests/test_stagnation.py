import unittest

from shiftopt import run_pipeline, stagnation_policy


class StagnationTests(unittest.TestCase):
    def test_resets_after_improvement_and_cycles_after_consecutive_misses(self):
        proposals = iter((None, 8, 8, 9, 7))
        build = lambda *_: 10
        first = lambda *_: next(proposals)
        second = lambda *_: None
        steps = [build, first, second]
        trace = []
        plan = run_pipeline(
            steps, int, policy=stagnation_policy([first, second], prefix=[build], patience=2),
            max_steps=8, on_step=lambda step, *_: trace.append(step),
        )
        self.assertEqual(trace, [build, first, first, first, first, second, second, first])
        self.assertEqual(plan, 7)

    def test_failed_construction_stops_and_initial_plan_skips_empty_prefix(self):
        build = lambda *_: None
        improve = lambda n, _: n - 1
        policy = stagnation_policy([improve], prefix=[build])
        self.assertIsNone(run_pipeline([build, improve], int, policy=policy, max_steps=2))
        self.assertEqual(run_pipeline([improve], int, initial=3, policy=stagnation_policy([improve]),
                                      max_steps=2), 1)

    def test_invalid_parameters(self):
        step = lambda *_: None
        for steps, patience in (([], 1), ([step, step], 1), ([step], 0)):
            with self.assertRaises(ValueError):
                stagnation_policy(steps, patience=patience)
