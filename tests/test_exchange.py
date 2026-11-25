import unittest

from shiftopt import ejection_chain, run_pipeline


class ExchangeTests(unittest.TestCase):
    def test_backtracks_and_continues_past_an_inferior_closure(self):
        visits = []
        def extend(plan, chain, rng):
            return {"root": ("dead end", "middle"), "middle": ("end",)}.get(chain, ())

        def close(plan, chain):
            visits.append(chain)
            return {"root": 6, "middle": 5, "end": 1}.get(chain)

        for depth, nodes, expected in [(2, 4, 5), (3, 3, 5), (3, 4, 1)]:
            visits.clear()
            step = ejection_chain(lambda plan, rng: "root", extend, close, int,
                                  max_depth=depth, max_nodes=nodes, attempts=1)
            self.assertEqual(run_pipeline([step], int, initial=5), expected)
            self.assertLessEqual(len(visits), nodes)
        self.assertEqual(visits, ["root", "dead end", "middle", "end"])

    def test_next_attempt_uses_accepted_plan(self):
        seen = []
        def start(plan, rng):
            seen.append(plan)
            return plan - 1
        step = ejection_chain(start, lambda *_: (), lambda plan, chain: chain, int,
                              max_depth=1, max_nodes=1, attempts=3)
        self.assertEqual(run_pipeline([step], int, initial=5), 2)
        self.assertEqual(seen, [5, 4, 3])

    def test_deadline_and_invalid_limits(self):
        def unexpected(*args):
            self.fail("called after deadline")
        step = ejection_chain(unexpected, unexpected, unexpected, int,
                              max_depth=1, max_nodes=1, attempts=1)
        self.assertEqual(step(3, 0), 3)
        for depth, nodes in ((0, 1), (1, -1)):
            with self.assertRaises(ValueError):
                ejection_chain(None, None, None, int, max_depth=depth, max_nodes=nodes, attempts=1)
