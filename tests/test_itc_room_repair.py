from importlib import import_module
from math import inf
import unittest

from demos.itc.timetable import Timetable
from shiftopt import run_pipeline

repair = import_module("demos.itc.2007.room_repair")


def cost(positions):
    return int(positions[0][0] != 1)


def problem(rooms):
    return Timetable([[0, 1], [1]], rooms, [0, 0], [1, 1], [[1, 1]] * 2, [[], []], 2, cost)


class RoomRepairTests(unittest.TestCase):
    def test_moves_event_to_occupied_room_and_reassigns_occupant(self):
        initial = 1, ((0, 0), (1, 0))
        step = repair.room_repair(problem([[0], [0, 1]]), attempts=100, seed=1)
        best = run_pipeline([step], lambda p: p[0], initial=initial)
        self.assertEqual(best, (0, ((1, 0), (1, 1))))
        self.assertEqual(initial, (1, ((0, 0), (1, 0))))

    def test_failed_matching_and_precedence_never_escape_to_pipeline(self):
        initial = 1, ((0, 0), (1, 0))
        p = problem([[0], [0]])
        for _ in range(2):
            step = repair.room_repair(p, attempts=100, seed=1)
            self.assertEqual(step(initial, inf), initial)
            p.rooms[1] = [0, 1]
            p.relations = [[(1, "before")], [(0, "after")]]

    def test_conflicting_students_move_as_one_component(self):
        p = problem([[0], [0]])
        p.periods[1] = [0, 1]
        p.clashes = [2, 1]
        plan = 1, ((0, 0), (1, 0))
        step = repair.room_repair(p, attempts=100, seed=1)
        self.assertEqual(step(plan, inf), (0, ((1, 0), (0, 0))))
