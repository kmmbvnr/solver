import unittest

from shiftopt import bounded_max_flow


class FlowTests(unittest.TestCase):
    def test_redirects_feasible_flow_to_maximize_delivery(self):
        edges = [(0, 1, 2., 2.), (1, 0, 0., 2.), (1, 2, .5, 1.5)]
        self.assertEqual(bounded_max_flow(3, edges, 0, 2), [2., .5, 1.5])

    def test_unmet_lower_bound(self):
        self.assertIsNone(bounded_max_flow(3, [(1, 2, 1., 2.)], 0, 2))
