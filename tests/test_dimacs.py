"""Exercise each edition through the public CLI and check its example solution."""
import json
from math import dist
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1] / "demos" / "dimacs"


class DimacsExamples(unittest.TestCase):
    def solve(self, year):
        raw = subprocess.check_output([sys.executable, ROOT / "run.py", str(year)])
        result = json.loads(raw)
        return result["solution"], result["pipeline_score"]

    def test_graph_editions(self):
        colors, count = self.solve(1992)
        edges = [(1, 2), (2, 3), (3, 1), (2, 4), (3, 5), (4, 6), (5, 6)]
        self.assertEqual(len(colors), 6)
        self.assertTrue(all(colors[a-1] != colors[b-1] for a, b in edges))
        self.assertEqual(len(set(colors)), count)
        self.assertEqual(count, 3)
        side, cut = self.solve(2012)
        self.assertEqual(sorted(side), [0, 0, 0, 1, 1, 1])
        self.assertEqual(side[:3], [side[0]] * 3)
        self.assertEqual(cut, 1)
        tree, _ = self.solve(2014)
        self.assertEqual(sorted(sorted(edge) for edge in tree["edges"]), [[1, 2], [2, 3], [2, 4]])
        self.assertEqual(tree["cost"], 3)

    def test_reversals(self):
        permutation = [1, -4, -3, -2, 5]
        moves, _ = self.solve(1994)
        for start, end in moves:
            permutation[start-1:end] = [-v for v in reversed(permutation[start-1:end])]
        self.assertEqual(permutation, list(range(1, 6)))

    def test_tour(self):
        tour, length = self.solve(2001)
        coords = [(0, 0), (3, 0), (3, 4), (0, 4)]
        self.assertEqual(sorted(tour), [1, 2, 3, 4])
        self.assertEqual(sum(dist(coords[tour[i-1]-1], coords[v-1]) for i, v in enumerate(tour)), length)
        self.assertEqual(length, 14)

    def test_inventory_routing(self):
        result, score = self.solve(2020)
        inventory = [10, 2, 2]
        points = [(0, 0), (3, 0), (3, 4)]
        travel = holding = 0.
        self.assertEqual(len(result["routes"]), 2)
        for day in result["routes"]:
            route, = day
            self.assertLessEqual(sum(q for i, q in route), 10)
            self.assertEqual(len({i for i, q in route}), len(route))
            stops = [0, *(i for i, q in route), 0]
            travel += sum(dist(points[i], points[j]) for i, j in zip(stops, stops[1:]))
            for i, qty in route:
                self.assertIsInstance(qty, int)
                self.assertGreater(qty, 0)
                inventory[i] += qty
                inventory[0] -= qty
                self.assertLessEqual(inventory[i], 8)
            inventory = [inventory[0]+5, inventory[1]-3, inventory[2]-3]
            self.assertGreaterEqual(min(inventory), 0)
            holding += sum(i*h for i, h in zip(inventory, (0.1, 0.3, 0.2)))
        self.assertAlmostEqual(result["holding"], holding)
        self.assertAlmostEqual(score, holding + travel)
