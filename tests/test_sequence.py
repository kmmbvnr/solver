import unittest

from shiftopt import bandit_policy, run_pipeline
from shiftopt.sequence import move_sequence


class SequenceTests(unittest.TestCase):
    def test_controller_rewards_the_complete_sequence(self):
        visited = []
        def displace(plan, deadline):
            return plan + 1
        def repair(plan, deadline):
            visited.append(plan)
            return plan - 3
        step = move_sequence(displace, repair)
        rewards = []
        policy = bandit_policy([step])
        def observe(plan, history, remaining):
            if history:
                rewards.append(history[-1].reward)
                return None
            return policy(plan, history, remaining)
        saved = []
        self.assertEqual(run_pipeline([step], int, initial=5, policy=observe, max_steps=2,
                                      gain=lambda old,new: old-new, on_accept=saved.append), 3)
        self.assertEqual((visited, rewards, saved), ([6], [2], [3]))

    def test_declined_or_expired_sequence_returns_no_partial_plan(self):
        def fail(*args):
            self.fail("unexpected move")
        self.assertIsNone(move_sequence(fail)(1, 0))
        step = move_sequence(lambda *_: 7, lambda *_: None, fail)
        self.assertEqual(run_pipeline([step], int, initial=8), 8)
        with self.assertRaises(ValueError):
            move_sequence()
