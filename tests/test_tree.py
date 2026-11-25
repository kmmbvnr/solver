import unittest
from unittest.mock import patch

from shiftopt.tree import bounded_best_first


class TreeTests(unittest.TestCase):
    def test_wider_restart_recovers_a_pruned_branch(self):
        tree = {"root": ["a","b"], "a": [9], "b": [2]}
        options = dict(key=lambda n:n, priority=lambda n: {"root":0, "a":0, "b":1}[n],
                       complete=lambda n:isinstance(n,int), score=int, lower_bound=lambda n:0,
                       deadline=float("inf"))
        self.assertEqual(bounded_best_first("root", tree.get, limits=(1,), **options), 9)
        self.assertEqual(bounded_best_first("root", tree.get, limits=(1,2), **options), 2)

    def test_bound_prunes_without_using_guide_as_a_bound(self):
        def expand(n):
            self.assertNotEqual(n, "bad")
            return [7, "bad", "good"] if n=="root" else [3]
        result = bounded_best_first("root", expand, key=str, priority=lambda n:99 if n=="good" else 0,
                                    complete=lambda n:isinstance(n,int), score=int,
                                    lower_bound=lambda n:8 if n=="bad" else 0,
                                    limits=[3], deadline=float("inf"))
        self.assertEqual(result,3)

    def test_deadline_returns_last_complete_candidate(self):
        def expand(n):
            yield 5
            clock[0] = 10
            yield 2
        clock = [0]
        with patch("shiftopt.tree.monotonic", side_effect=lambda:clock[0]):
            best = bounded_best_first(10, expand, key=int, priority=int, complete=lambda n:n<10,
                                      score=int, lower_bound=lambda _:0, limits=[1], deadline=5)
        self.assertEqual(best,5)
