import unittest
import numpy as np
from fbsim_paper.baselines import base_rates, change_quantiles


class BaseRates(unittest.TestCase):
    def test_leaves_out_own_world(self):
        items = [dict(world="a", t="x", q=0.1), dict(world="b", t="x", q=0.3), dict(world="c", t="x", q=0.8)]
        self.assertEqual(base_rates(items, [lambda it: it["t"]]), [0.55, 0.45, 0.2])

    def test_falls_back_to_next_key(self):
        # "y" exists only in world a, so its item takes the rate over every template in the other worlds
        items = [dict(world="a", t="x", q=0.2), dict(world="a", t="y", q=0.9), dict(world="b", t="x", q=0.4)]
        rates = base_rates(items, [lambda it: it["t"], lambda it: 0])
        self.assertEqual(rates, [0.4, 0.4, 0.2])


class ChangeQuantiles(unittest.TestCase):
    def test_adds_scaled_changes_and_clips(self):
        q = change_quantiles(10, [np.array([-30.0, 0.0]), np.array([2.0])], [0.0, 0.5, 1.0], scale=2.0, lo=0, hi=12)
        np.testing.assert_allclose(q, [0, 10, 12])


if __name__ == "__main__":
    unittest.main()
