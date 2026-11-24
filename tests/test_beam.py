import unittest
from time import monotonic

from shiftopt import beam_search


class BeamSearchTests(unittest.TestCase):
    def test_duplicate_states_share_one_frontier_slot(self):
        edges = {
            "start": [("a", 4), ("a", 2), ("b", 3), ("c", 8)],
            "a": [],
            "b": [("finish", 3)],
            "c": [("finish", 1)],
        }
        visits = []

        def expand(state):
            name, cost = state
            visits.append(state)
            return edges[name]

        result = beam_search(
            ("start", 0),
            expand,
            key=lambda s: s[0],
            priority=lambda s: s[1],
            complete=lambda s: s[0] == "finish",
            width=2,
            deadline=float("inf"),
        )
        self.assertEqual(result, ("finish", 3))
        self.assertEqual(visits, [("start", 0), ("a", 2), ("b", 3)])

    def test_expired_deadline_prevents_expansion(self):
        result = beam_search(
            0,
            lambda s: self.fail("expanded after deadline"),
            key=int,
            priority=int,
            complete=lambda s: False,
            width=1,
            deadline=monotonic(),
        )
        self.assertIsNone(result)
