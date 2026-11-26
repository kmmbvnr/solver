import unittest
from importlib import import_module
from math import inf
from pathlib import Path
from tempfile import TemporaryDirectory

from demos.itc.events import read_events

ThreeEventChains = import_module("demos.itc.2007.chains").ThreeEventChains


class ThreeEventTests(unittest.TestCase):
    def setUp(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.tim"
            path.write_text("3 1 0 3\n10\n1 0 0\n0 1 0\n0 0 1\n")
            self.problem = read_events(path, False)
        self.problem.periods = [[8, 0], [0, 1], [1, 2]]
        self.initial = (4, ((8, 0), (0, 0), (1, 0)))

    def test_closes_three_displacements_and_restores_occupancy(self):
        step = ThreeEventChains(self.problem, 3, attempts=100)
        best = step(self.initial, inf)
        self.assertEqual(best, (3, ((0, 0), (1, 0), (2, 0))))
        self.assertEqual(step.improved, 1)
        self.assertGreaterEqual(step.feasible, 1)
        self.assertEqual(tuple(step.state.positions), step.base)
        self.assertEqual(best[0], self.problem.objective(best[1]))

    def test_open_chain_preserves_the_incumbent(self):
        self.problem.periods[2] = [1]
        step = ThreeEventChains(self.problem, 3, attempts=100)
        self.assertIs(step(self.initial, inf), self.initial)
        self.assertEqual(step.improved, 0)
        self.assertEqual(tuple(step.state.positions), self.initial[1])

    def test_three_moves_must_jointly_respect_precedence(self):
        self.problem.relations = [[(2, "after")], [], [(0, "before")]]
        step = ThreeEventChains(self.problem, 3, attempts=100)
        self.assertIs(step(self.initial, inf), self.initial)
        self.assertEqual(tuple(step.state.positions), self.initial[1])
