import unittest

from shiftopt import run_pipeline
from shiftopt.reassign import reassignment_search


class ReassignmentTests(unittest.TestCase):
    def test_rebuild_uses_last_accepted_assignment_and_full_cost(self):
        seen = []
        def rebuild(plan, transfer, deadline):
            seen.append(plan)
            if transfer is None:
                return None
            return transfer
        candidates = [(2, 8), None, (3, 1), (1, 5), (0, 0)]
        step = reassignment_search(lambda _: candidates, rebuild, sum, attempts=4)
        result = run_pipeline([step], sum, initial=(4, 3))
        self.assertEqual(result, (3, 1))
        self.assertEqual(seen, [(4, 3), (4, 3), (4, 3), (3, 1)])

    def test_expired_or_empty_budget_preserves_incumbent(self):
        def unexpected(*args):
            self.fail("called after the budget expired")
        for attempts, deadline in ((0, float("inf")), (3, 0)):
            step = reassignment_search(unexpected, unexpected, unexpected, attempts=attempts)
            self.assertEqual(step(4, deadline), 4)
