import unittest

from shiftopt import bandit_policy, run_pipeline


class BanditTests(unittest.TestCase):
    def test_rewards_choose_operator_and_reset_between_runs(self):
        trace = []
        def build(*args):
            trace.append("build")
            return 20
        def small(n, deadline):
            trace.append("small")
            return n - 1
        def large(n, deadline):
            trace.append("large")
            return n - 3

        steps = [build, small, large]
        policy = bandit_policy([small, large], construct=build, exploration=0)
        for _ in range(2):
            trace.clear()
            best = run_pipeline(steps, int, policy=policy, max_steps=4, gain=lambda a, b: a-b)
            self.assertEqual(best, 13)
            self.assertEqual(trace, ["build", "small", "large", "large"])

    def test_exploration_retries_a_missed_operator(self):
        calls = []
        def productive(n, deadline):
            return n - 1
        def misses(*args):
            calls.append(None)
        steps = [productive, misses]
        run_pipeline(steps, int, initial=50, policy=bandit_policy(steps, exploration=3),
                     max_steps=12)
        self.assertGreater(len(calls), 1)

    def test_invalid_reward_and_construction_failure(self):
        step = lambda n, deadline: n - 1
        policy = bandit_policy([step])
        for reward in [-1, float("inf"), float("nan")]:
            with self.assertRaises(ValueError):
                run_pipeline([step], int, initial=3, policy=policy, max_steps=1,
                             gain=lambda a, b: reward)
        build = lambda *_: None
        self.assertIsNone(run_pipeline([build, step], int,
                                       policy=bandit_policy([step], construct=build), max_steps=3))
