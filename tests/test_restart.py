import unittest

from shiftopt.restart import restart_strength


class RestartTests(unittest.TestCase):
    def test_growth_cap_and_reset(self):
        choose = restart_strength(2, 7)
        self.assertEqual([choose(gain) for gain in (True, False, False, False, True)],
                         [2, 4, 7, 7, 2])

    def test_invalid_bounds(self):
        for low, high in ((0, 2), (3, 2), (1, 2.5)):
            with self.assertRaises(ValueError):
                restart_strength(low, high)
