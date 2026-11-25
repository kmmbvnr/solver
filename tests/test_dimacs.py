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

    def test_flow_editions(self):
        for year, value in [(1990, 9), (2026, 33)]:
            solution, _ = self.solve(year)
            x, y, z, a, b = solution["flows"]
            self.assertEqual(x, z + a)
            self.assertEqual(y + z, b)
            self.assertEqual(x + y, 9)
            self.assertTrue(all(0 <= flow <= cap for flow, cap in
                                zip((x, y, z, a, b), (6, 4 if year == 1990 else 6,
                                                       2 if year == 1990 else 4, 3, 6))))
            if year == 1990:
                self.assertEqual(solution["value"], value)
            else:
                self.assertGreaterEqual(x, 1)
                self.assertEqual(2*x + 4*y - z + 2*a + b, value)
                self.assertEqual(solution["cost"], value)

    def test_graph_editions(self):
        colors, count = self.solve(1992)
        edges = [(1, 2), (2, 3), (3, 1), (2, 4), (3, 5), (4, 6), (5, 6)]
        self.assertEqual(len(colors), 6)
        self.assertTrue(all(colors[a-1] != colors[b-1] for a, b in edges))
        self.assertEqual(len(set(colors)), count)
        self.assertEqual(count, 3)
        groups, _ = self.solve(1993)
        self.assertEqual(groups, [0, 0, 0, 0, 1, 1, 1, 2])
        distances, _ = self.solve(2005)
        self.assertEqual(distances, [0, 3, 2, 6, None])
        side, cut = self.solve(2012)
        self.assertEqual(sorted(side), [0, 0, 0, 1, 1, 1])
        self.assertEqual(side[:3], [side[0]] * 3)
        self.assertEqual(cut, 1)
        tree, _ = self.solve(2014)
        self.assertEqual(sorted(sorted(edge) for edge in tree["edges"]), [[1, 2], [2, 3], [2, 4]])
        self.assertEqual(tree["cost"], 3)

    def test_reversals_and_queries(self):
        permutation = [1, -4, -3, -2, 5]
        moves, _ = self.solve(1994)
        for start, end in moves:
            permutation[start-1:end] = [-v for v in reversed(permutation[start-1:end])]
        self.assertEqual(permutation, list(range(1, 6)))
        extracted, _ = self.solve(1995)
        self.assertEqual(extracted, [3, -1, 8, 8])
        neighbors, _ = self.solve(1998)
        self.assertEqual(neighbors, {"index": [0, 1], "distance": [1., 1.]})

    def test_relaxation_and_tour(self):
        result, _ = self.solve(2000)
        factors = result["factor"]
        self.assertEqual(len(factors), 3)
        for row in factors:
            self.assertAlmostEqual(sum(x*x for x in row), 1)
        value = sum(1 - sum(x*y for x, y in zip(factors[i-1], row))
                    for i, row in enumerate(factors))
        self.assertAlmostEqual(value, result["objective"])
        self.assertAlmostEqual(value, 4.5)
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
