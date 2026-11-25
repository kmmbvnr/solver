"""Check witness properties and edge cases in the PACE pipelines."""

import runpy
import unittest
from ast import literal_eval
from io import StringIO
from pathlib import Path

from shiftopt.cover import greedy_cover
from shiftopt.elimination import eliminate

ROOT = Path(__file__).resolve().parents[1] / "demos" / "pace"


def run_demo(task, text, seconds=2):
    solve = runpy.run_path(str(ROOT / task / "solve.py"))["solve"]
    return solve(StringIO(text), seconds)


class PaceDemoTests(unittest.TestCase):
    def test_greedy_cover_recomputes_stale_marginal_gains(self):
        sets = {1: {1, 2, 3}, 2: {1, 2}, 3: {4, 5}}
        self.assertEqual(
            greedy_cover(None, float("inf"), sets=sets, universe=set(range(1, 6))),
            [1, 3],
        )

    def test_cycle_elimination(self):
        graph = {1: {2, 4}, 2: {1, 3}, 3: {2, 4}, 4: {1, 3}}
        bags, fill = eliminate(graph, float("inf"), min_fill=True)
        self.assertEqual(len(fill), 1)
        self.assertNotIn(fill[0][1], graph[fill[0][0]])
        self.assertEqual(max(len(row) for _, row in bags), 2)

    def test_directed_cycle_with_empty_adjacency_line(self):
        size, deleted = run_demo(
            "2022/directed_feedback_vertex_set", "4 3 0\n2\n3\n1\n\n"
        )
        self.assertEqual(size, 1)
        self.assertIn(deleted[0], {1, 2, 3})

    def test_cluster_kernel_uses_original_vertex_ids_for_lifting(self):
        graph = "p cep 5 3\n1 3\n2 4\n4 5\n"
        size, lines = run_demo("2021/kernelization", graph)
        self.assertEqual((size, lines[:2]), (3, [0, "p cep 3 2"]))
        it = iter(lines[4:])
        for _ in range(4):
            edits = [tuple(map(int, next(it).split())) for _ in range(next(it))]
            self.assertTrue(all({a, b} <= {2, 4, 5} for a, b in edits))
            edges = {(1, 3), (2, 4), (4, 5)} ^ {tuple(sorted(e)) for e in edits}
            for a, b in edges:
                for c, d in edges:
                    if b == c:
                        self.assertIn(tuple(sorted((a, d))), edges)
        self.assertIsNone(next(it, None))

    def test_crossings_ignore_shared_endpoints_and_read_cutwidth(self):
        text = "p ocr 2 2 4 2\n1\n3\n2\n4\n1 3\n1 4\n2 3\n2 4\n"
        count, order = run_demo("2024/crossing_minimization", text)
        self.assertEqual((count, set(order)), (1, {3, 4}))

    def test_forest_ignores_sibling_order_across_three_trees(self):
        text = "#p 3 3\n((1,2),3);\n(3,(2,1));\n((2,1),3);\n"
        count, forest = run_demo("2026/agreement_forest", text)
        self.assertEqual(count, 1)
        self.assertEqual(str(literal_eval(forest[0][:-1])).count(","), 2)

    def test_weighted_path_absence_and_timeout(self):
        text = "p digraph 3 1 2\na 1 2 3\n"
        self.assertEqual(run_demo("2027/k_path", text), (0, ["0 0"]))
        with self.assertRaises(ValueError):
            run_demo("2027/k_path", text, seconds=0)
