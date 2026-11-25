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

    def test_checkpoints_only_accepted_proposals(self):
        proposals = iter([None, 3, 3, 4, 1])
        saved = []
        result = run_pipeline([lambda plan, deadline: next(proposals)] * 5, int,
                              on_accept=saved.append)
        self.assertEqual(saved, [3, 1])
        self.assertEqual(result, 1)

    def test_policy_can_repeat_switch_and_stop(self):
        def build(best, deadline):
            return 5

        def improve(best, deadline):
            return max(4, best - 1)

        seen = []
        def policy(best, history, remaining):
            self.assertGreater(remaining, 0)
            seen.append((best, [trial.accepted for trial in history]))
            if not history:
                return build
            if history[-1].accepted:
                return improve
            return None

        result = run_pipeline([build, improve], int, policy=policy, max_steps=5)
        self.assertEqual(result, 4)
        self.assertEqual(seen, [(None, []), (5, [True]), (4, [True, True]),
                                (4, [True, True, False])])

    def test_policy_limits_and_available_steps(self):
        def step(best, deadline):
            return (best or 0) + 1
        def choose(*args):
            return step
        self.assertEqual(run_pipeline([step], lambda n: -n, policy=choose, max_steps=3), 3)
        self.assertIsNone(run_pipeline([step], int, policy=choose, max_steps=2, seconds=0))
        with self.assertRaises(ValueError):
            run_pipeline([step], int, policy=choose)
        with self.assertRaises(ValueError):
            run_pipeline([], int, policy=choose, max_steps=1)
