import unittest
from math import inf
from shiftopt import ResumableAnnealing, simulated_annealing


def trace_move(trace, current, rng, deadline):
    proposal = current + rng.choice((-1, 1, 3))
    trace.append((current, proposal))
    return proposal


class ResumeTests(unittest.TestCase):
    def test_pause_and_cycle_match_two_uninterrupted_runs(self):
        from functools import partial
        expected, actual = [], []
        best = 100
        for seed in (3, 4):
            step = simulated_annealing(partial(trace_move, expected), int, attempts=25, temperature=8, seed=seed)
            best = step(best, inf)
        step = ResumableAnnealing(partial(trace_move, actual), int, attempts=10, cycle_attempts=25,
                                 temperature=8, seed=3)
        result = 100
        for _ in range(5):
            result = step(result, inf)
        self.assertEqual((actual, result), (expected, best))
        self.assertEqual(step(-1000, 0), -1000)

    def test_better_external_incumbent_replaces_current_mid_cycle(self):
        from functools import partial
        trace = []
        step = ResumableAnnealing(partial(trace_move, trace), int, attempts=1, cycle_attempts=10,
                                 temperature=8, seed=12)
        step(50, inf)
        step(-1000, inf)
        self.assertEqual(trace[-1][0], -1000)
        self.assertEqual(step.position, 2)
