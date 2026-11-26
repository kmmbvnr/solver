import unittest
from random import Random
from pathlib import Path
from tempfile import TemporaryDirectory

from demos.itc.events import displace_event, read_events
from demos.itc.timetable import Occupancy, TimetableMoves


class DisplacementTests(unittest.TestCase):
    def setUp(self):
        # One room, two events and one shared student. Event 1 cannot use period 0.
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.tim"
            path.write_text("2 1 0 1\n10\n1 1\n")
            self.problem = read_events(path, False)
        self.problem.periods = [[0, 1], [1, 2]]
        self.positions = ((0, 0), (1, 0))

    def test_rehouses_blocker_in_a_third_period(self):
        state = Occupancy(self.problem, self.positions)
        changes = displace_event(state, 0, 1, Random(1))
        self.assertEqual(changes, [(0, 1, 0), (1, 2, 0)])
        self.assertEqual(tuple(state.positions), self.positions)
        self.assertTrue(state.apply(changes))
        self.assertEqual(tuple(state.positions), ((1, 0), (2, 0)))

    def test_rejected_relocation_restores_the_original_plan(self):
        self.problem.relations = [[(1, "after")], [(0, "before")]]
        # Start with event 0 after event 1; the proposed reassignment reverses them.
        self.problem.periods[0] = [1, 3]
        positions = ((3, 0), (1, 0))
        state = Occupancy(self.problem, positions)
        changes = displace_event(state, 0, 1, Random(1))
        self.assertTrue(changes)
        self.assertFalse(state.apply(changes))
        self.assertEqual(tuple(state.positions), positions)

    def test_cached_neighborhood_agrees_with_full_scoring(self):
        move = TimetableMoves(self.problem, ("displace",))
        rng = Random(42)
        plan = self.problem.objective(self.positions), self.positions
        for k in range(80):
            proposal = move(plan, rng, float("inf"))
            if proposal is not None:
                self.assertEqual(proposal[0], self.problem.objective(proposal[1]))
                self.assertNotEqual(proposal[1][0][0], proposal[1][1][0])
                if k % 2:
                    plan = proposal
