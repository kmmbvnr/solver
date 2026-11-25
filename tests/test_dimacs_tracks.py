"""Replay the small DIMACS examples, including variants that share a parser."""

import importlib.util
import json
import subprocess
import sys
import unittest
from collections import Counter
from itertools import combinations
from math import isclose
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "demos" / "dimacs"


def run(track, instance=None, *options):
    script = ROOT / track / "solve.py"
    inputs = [str(script.with_name(instance))] if instance else []
    return json.loads(
        subprocess.check_output([sys.executable, str(script), *inputs, *options])
    )


class Tracks(unittest.TestCase):
    def test_clique_and_sat_witnesses(self):
        r = run("1992/clique")
        self.assertEqual(len(r["solution"]), -r["pipeline_score"])
        self.assertTrue(
            all(
                tuple(sorted(pair)) in {(1, 2), (2, 3), (1, 3), (2, 4), (4, 5)}
                for pair in combinations(r["solution"], 2)
            )
        )
        r = run("1992/sat")
        assignment = set(r["solution"])
        self.assertEqual(r["status"], "SAT")
        self.assertTrue(
            all(assignment.intersection(c) for c in ((1, 2), (-1, 2), (-2, 3), (1, -3)))
        )

    def test_matching_flow_and_cut(self):
        g = run("1990/general_matching")
        self.assertEqual(set(map(tuple, g["solution"])), {(1, 2), (3, 4)})
        for file in (None, "cardinality.txt"):
            r = run("2026/matching", file)
            self.assertEqual(set(map(tuple, r["solution"])), {(1, 4), (2, 3)})
            self.assertEqual(r["pipeline_score"], -2 if file else -14)
        r = run("2026/max_flow")
        balance = Counter()
        arcs = [(1, 2), (1, 3), (2, 4), (2, 5), (3, 4), (4, 6), (5, 6)]
        for x, (a, b) in zip(r["solution"], arcs, strict=True):
            self.assertIn(x, (0, 1))
            balance[a] += x
            balance[b] -= x
        self.assertEqual(dict((v, x) for v, x in balance.items() if x), {1: 2, 6: -2})
        side = set(r["source_side_min_cut"])
        self.assertEqual(sum(a in side and b not in side for a, b in arcs), 2)
        self.assertEqual(run("2026/min_cost_flow")["solution"], [1, 3, 3])
        self.assertIn(set(run("2026/global_cut")["solution"]), ({1, 2, 3}, {4, 5, 6}))

    def test_metric_and_path_problems(self):
        self.assertEqual(run("1998/approximate_neighbors")["solution"], [0, 1])
        r = run("2000/torus")
        vectors = r["solution"]
        self.assertTrue(all(isclose(sum(x * x for x in row), 1.0) for row in vectors))
        value = sum(
            1 - sum(a * b for a, b in zip(u, v)) for u, v in combinations(vectors, 2)
        )
        self.assertAlmostEqual(value, -r["pipeline_score"])
        r = run("2001/asymmetric")
        tour = r["solution"]
        self.assertEqual(sorted(tour), [1, 2, 3, 4])
        cost = [[0, 9, 2, 6], [2, 0, 8, 4], [8, 5, 0, 2], [8, 2, 5, 0]]
        self.assertEqual(
            sum(cost[tour[i - 1] - 1][v - 1] for i, v in enumerate(tour)),
            r["pipeline_score"],
        )
        r = run("2005/paths")
        self.assertTrue(r["certified"])
        self.assertEqual(r["solution"]["distance"], [0, 3, 2, 6, None])

    @unittest.skipUnless(
        importlib.util.find_spec("cvxpy"), "requires the dimacs-conic extra"
    )
    def test_conic_trace_and_psd(self):
        a, b, c, d = run("2000/conic")["solution"]
        self.assertAlmostEqual(a + d, 1.0, places=5)
        self.assertAlmostEqual(b, c, places=5)
        self.assertGreaterEqual(min(a, d, a * d - b * c), -1e-5)
        self.assertAlmostEqual(b + c, 1.0, places=5)

    def test_partition_and_clustering(self):
        r = run("2012/kway", None, "--parts", "3", "--objective", "cut")
        self.assertEqual(sorted(Counter(r["solution"]).values()), [2, 2, 2])
        self.assertAlmostEqual(run("2012/clustering")["modularity"], 5 / 14)
        mix = run("2012/mix")["solution"]
        self.assertEqual(len(set(mix["labels"])), 2)
        self.assertAlmostEqual(mix["metrics"]["performance"], 14 / 15)

    def test_steiner_variants(self):
        for file, vertices, score in (
            (None, {1, 2, 3, 4}, 4),
            ("unrooted.txt", {1, 2, 3}, 4),
            ("node_weights.txt", {1, 2, 3}, -7),
        ):
            r = run("2014/prize_tree", file)
            self.assertEqual(set(r["solution"]["vertices"]), vertices)
            self.assertEqual(r["pipeline_score"], score)
        tree = run("2014/degree_tree")["solution"]
        self.assertEqual(
            Counter(v for a, b, w in tree for v in (a, b)), {1: 1, 2: 1, 3: 1, 4: 3}
        )
        self.assertEqual(run("2014/budget_tree")["solution"]["edges"], [[1, 2], [2, 3]])

    def test_service_routes(self):
        for file, required in (
            (None, {1, 2, 3}),
            ("mixed.txt", {"E1", "A1", "N2"}),
            ("time_dependent.txt", {"1-2"}),
        ):
            r = run("2020/arc_routing", file)
            served = [s[0] for route in r["solution"] for s in route["services"]]
            self.assertCountEqual(served, required)
            self.assertEqual(
                sum(trip["duration"] for trip in r["solution"]), r["pipeline_score"]
            )
            if file == "time_dependent.txt":
                self.assertEqual(r["pipeline_score"], 7)
        r = run("2020/cvrp")
        self.assertCountEqual(
            [v for route in r["solution"] for v in route], [2, 3, 4, 5]
        )
        for route in r["solution"]:
            self.assertLessEqual(sum([0, 0, 3, 4, 3, 4][v] for v in route), 8)
        quantities = Counter()
        for route in run("2020/split_delivery")["solution"]:
            self.assertLessEqual(sum(q for v, q in route), 10)
            for v, q in route:
                quantities[v] += q
        self.assertEqual(quantities, {1: 7, 2: 6, 3: 3, 4: 4})
        r = run("2020/time_windows")
        self.assertLessEqual(len(r["solution"]), 2)
        self.assertCountEqual([v for route in r["solution"] for v in route], [1, 2, 3])
        for k in ("0", "1", "2"):
            r = run("2020/electric", None, "--chargers", k)
            self.assertCountEqual(
                [
                    v["customer"]
                    for trip in r["solution"]
                    for v in trip["visits"]
                    if "customer" in v
                ],
                [1, 2],
            )
        r = run("2020/ride_hailing")
        self.assertEqual(r["solution"]["req_assgts"], [1, 0])
