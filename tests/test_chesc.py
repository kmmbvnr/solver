"""Integration checks against the corrected competition JARs."""
import importlib
import importlib.util
import os
import unittest
from pathlib import Path

home = Path(os.environ.get("HYFLEX_HOME", "."))
available = importlib.util.find_spec("jpype") and all(
    (home / jar).is_file() for jar in ("chesc-ps.jar", "chesc-fixed-no-ps.jar")
)


@unittest.skipUnless(available, "requires the CHeSC extra and HYFLEX_HOME")
class HyFlexTests(unittest.TestCase):
    def test_2011_constructor_and_both_policies(self):
        solve = importlib.import_module("demos.chesc.2011.solve").solve
        initial, untouched = solve("sat", 3, 1, 10, 1, "fixed")
        self.assertEqual(untouched, initial)
        for policy in ("bandit", "fixed"):
            with self.subTest(policy=policy):
                start, best = solve("sat", 3, 1, 10, 20, policy)
                self.assertEqual(initial, start)
                self.assertLess(best, start)

    def test_2014_batch_preserves_all_results_in_input_order(self):
        solve_batch = importlib.import_module("demos.chesc.2014.solve").solve_batch
        jobs = [("sat", 5), ("sat", 3), ("flowshop", 1)]
        for workers in (1, 2):
            with self.subTest(workers=workers):
                results = solve_batch(jobs, workers, 60, 1, 8)
                self.assertEqual([row[:2] for row in results], jobs)
                for _, _, initial, best in results:
                    self.assertLessEqual(best, initial)
