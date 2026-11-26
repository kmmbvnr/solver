import unittest
from time import monotonic

import numpy as np

from shiftopt import run_pipeline, tabu_assignment
from shiftopt.tabu import _Penalties, _neighbors


class TabuAssignmentTests(unittest.TestCase):
    def test_resource_clashes_and_precedence_with_sparse_labels(self):
        slots = [[-5, 10, 30]] * 4
        rooms = [[9], [9], [9, 100], [100]]
        step = tabu_assignment(slots, rooms, [(1, 3), (3, 1)], [(0, 2), (2, 3)], seed=5)
        plan = run_pipeline([step], tuple, seconds=1)
        self.assertIsNotNone(plan)
        self.assertEqual(len(set(plan)), len(plan))
        for i, (t, r) in enumerate(plan):
            self.assertIn(t, slots[i])
            self.assertIn(r, rooms[i])
        self.assertLess(plan[0][0], plan[2][0])
        self.assertLess(plan[2][0], plan[3][0])
        self.assertNotEqual(plan[1][0], plan[3][0])

    def test_failed_construction_does_not_export_conflicts(self):
        step = tabu_assignment([[0], [0]], [[0], [0]], [])
        self.assertIsNone(run_pipeline([step], tuple, seconds=0.02))
        self.assertIsNone(tabu_assignment([[0]], [[]], [])(None, monotonic() + 1))
        self.assertEqual(tabu_assignment([], [], [])(None, monotonic() + 1), ())

    def test_weight_updates_survive_moving_either_endpoint(self):
        graph, _ = _neighbors(3, [(0, 1), (1, 2)], False)
        before, after = _neighbors(3, [(0, 1)], True)
        weights = _Penalties(graph, before, after, (3, 1))
        times = np.array([1, 1, 2])
        costs = np.zeros((3, 3), dtype=int)
        for i, t in enumerate(times):
            weights.update(costs, i, t, 1)
        weights.raise_violated(costs, times, np.array([[0], [2], [1]]), [0, 1])
        self.assertEqual(list(weights.room[:, 0]), [1, 2, 1])
        for i, t in [(2, 0), (0, 2), (1, 2), (0, 0)]:
            weights.update(costs, i, times[i], -1)
            times[i] = t
            weights.update(costs, i, t, 1)
            for slot in range(3):
                expected = [
                    2 * int(slot == times[1]) + 2 * int(slot >= times[1]),
                    2 * int(slot == times[0]) + int(slot == times[2]) + 2 * int(slot <= times[0]),
                    int(slot == times[1]),
                ]
                self.assertEqual(list(costs[:, slot]), expected)
