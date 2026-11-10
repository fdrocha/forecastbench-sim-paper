import importlib.util
import unittest
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr

_path = Path(__file__).resolve().parents[1] / "src/fbsim_paper/assets/combined/partial_correlations.py"
_spec = importlib.util.spec_from_file_location("partial_correlations", _path)
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


class PartialSpearman(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.z = rng.normal(size=30)
        self.x = self.z + rng.normal(size=30)
        self.y = self.z + rng.normal(size=30)

    def test_matches_closed_form(self):
        r = lambda a, b: spearmanr(a, b).statistic
        rxy, rxz, ryz = r(self.x, self.y), r(self.x, self.z), r(self.y, self.z)
        expected = (rxy - rxz * ryz) / np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
        self.assertAlmostEqual(pc.partial_spearman(self.x, self.y, self.z), expected, places=12)

    def test_nan_when_z_ranks_like_x(self):
        # x ranks exactly like z: nothing is left of x after z, so the partial is undefined
        self.assertTrue(np.isnan(pc.partial_spearman(2 * self.z + 1, self.y, self.z)))

    def test_interval_brackets_point(self):
        idx = np.random.default_rng(0).integers(0, 30, (500, 30))
        out = pc.partial_with_ci(self.x, self.y, self.z, idx)
        self.assertLessEqual(out["ci_lo"], out["rho"])
        self.assertLessEqual(out["rho"], out["ci_hi"])
        self.assertTrue(0 <= out["p"] <= 1)
        self.assertEqual(out["n"], 30)


if __name__ == "__main__":
    unittest.main()
