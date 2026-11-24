import unittest

from shiftopt import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_steps_receive_best_candidate(self):
        initial = (3, 0)
        proposals = iter([(2, 8), None, (4, 0), (2, 5)])
        seen = []

        def step(plan, deadline):
            seen.append(plan)
            return next(proposals)

        observations = []
        result = run_pipeline([step] * 4, tuple, initial=initial,
                              on_step=lambda *args: observations.append(args))
        self.assertEqual(seen, [initial, (2, 8), (2, 8), (2, 8)])
        self.assertEqual(result, (2, 5))
        self.assertEqual([o[2] for o in observations], [(2, 8), None, (4, 0), (2, 5)])

    def test_construction_and_expired_budget(self):
        def construct(plan, deadline):
            self.assertIsNone(plan)
            return 0

        self.assertEqual(run_pipeline([construct], int), 0)
        self.assertIsNone(run_pipeline([construct], int, seconds=0))
