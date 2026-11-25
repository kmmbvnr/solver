import unittest
from random import Random

from demos.itc.timetable import Occupancy, Timetable, TimetableMoves


class TimetableTests(unittest.TestCase):
    def test_rejects_overfilled_room_and_restores_displaced_events(self):
        p = Timetable(
            [range(2)] * 3, [[0]] * 3, [0] * 3, [10], [[5], [5], [1]], [[], [], []], 2, len
        )
        positions = ((0, 0), (0, 0), (1, 0))
        state = Occupancy(p, positions)
        self.assertFalse(state.apply([(2, 0, 0)]))
        self.assertEqual(tuple(state.positions), positions)
        self.assertEqual(state.used, [[10], [1]])
        p.exclusive = 1 << 2
        self.assertFalse(state.apply([(0, 1, 0)]))

    def test_cached_moves_preserve_constraints_after_acceptance_and_rejection(self):
        p = Timetable(
            [range(4)] * 3,
            [range(2)] * 3,
            [2, 1, 0],
            [1, 1],
            [[1, 1]] * 3,
            [[(2, "before")], [], [(0, "after")]],
            4,
            len,
        )
        move = TimetableMoves(p)
        plan = 3, ((0, 0), (1, 0), (2, 1))
        rng = Random(7)
        for i in range(100):
            proposal = move(plan, rng, float("inf"))
            if proposal is None:
                continue
            positions = proposal[1]
            self.assertEqual(len(set(positions)), 3)
            self.assertNotEqual(positions[0][0], positions[1][0])
            self.assertLess(positions[0][0], positions[2][0])
            if i % 2:
                plan = proposal
