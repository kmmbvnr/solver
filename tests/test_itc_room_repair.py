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

    def test_partial_room_move_evicts_then_repairs_across_calls(self):
        from random import Random
        p = problem([[0], [0, 1]])
        initial = 1, ((0, 0), (1, 0))
        partial_plan = repair.partial_room_move(p, initial, Random(4), inf)
        self.assertEqual(partial_plan, (0, ((1, 0), (1, -1))))
        self.assertGreater(repair.missing_room_penalty(partial_plan), 0)
        step = repair.partial_room_search(p, seed=4)
        self.assertEqual(step(initial, inf), (0, ((1, 0), (1, 1))))

    def test_mixed_search_filters_only_partial_proposals(self):
        from random import Random
        from unittest.mock import Mock

        p = problem([[0], [0, 1]])
        initial = 1, ((0, 0), (1, 0))
        ordinary = Mock(return_value=initial)
        strict = repair.MixedRoomMoves(p, ordinary, allow_partial=False)
        relaxed = repair.MixedRoomMoves(p, ordinary, allow_partial=True)
        rng = Mock()
        rng.randrange.return_value = 0
        rng.choice.side_effect = [1, 0, 1, 0]
        partial_plan = relaxed(initial, rng, inf)
        self.assertEqual(relaxed.penalty(partial_plan), 8)
        self.assertIsNone(strict(initial, rng, inf))
        rng.randrange.return_value = 1
        rng.choice.side_effect = [1, 1]
        repaired = relaxed(partial_plan, rng, inf)
        self.assertEqual(repaired, (0, ((1, 0), (1, 1))))
        ordinary.assert_not_called()
        self.assertEqual(strict(initial, Random(0), inf), initial)
        ordinary.assert_called_once()

    def test_precedence_penalty_counts_pairs_and_hides_infeasible_incumbents(self):
        from operator import itemgetter
        from shiftopt import ResumableAnnealing

        p = problem([[0], [1]])
        p.periods = [range(3), range(3)]
        p.slots = 3
        p.relations = [[(1, "before")], [(0, "after")]]
        initial = 20, ((0, 0), (1, 1))
        tied = 5, ((1, 0), (1, 1))
        reversed_plan = 4, ((1, 0), (0, 1))
        repaired = 1, ((1, 0), (2, 1))
        path = {initial: tied, tied: reversed_plan, reversed_plan: repaired}
        proposals = lambda plan, rng, deadline: path[plan]
        control = import_module("demos.itc.2007.solve").PrecedenceMoves
        strict = control(p, proposals, allow_violations=False)
        self.assertIsNone(strict(initial, None, inf))
        relaxed = control(p, proposals, allow_violations=True)
        self.assertEqual([relaxed.penalty(x) for x in path], [0, 8, 8])
        step = ResumableAnnealing(relaxed, itemgetter(0), attempts=1, cycle_attempts=10,
                                 temperature=8, penalty=relaxed.penalty)
        self.assertEqual([step(initial, inf) for _ in range(3)], [initial, initial, repaired])
