import unittest
from fbsim_paper.natcond import answers, independence, score

CELL = dict(cell_id=0, block="mechanical", city="kyoto", horizon_a=240, qid_a="A7", p_a=0.4, p_a_given_b=0.7,
            question_id_a="kyoto_T960_H240_A7", question_id_b="kyoto_T960_H144_A7")


class Answers(unittest.TestCase):
    def test_first_parsed_row_wins(self):
        rows = [dict(model="m", arm="t1", item="i", value=None), dict(model="m", arm="t1", item="i", value=0.3),
                dict(model="m", arm="t1", item="i", value=0.9)]
        self.assertEqual(answers(rows), {("m", "t1", "i"): 0.3})
        self.assertEqual(answers(rows, last=True), {("m", "t1", "i"): 0.9})


class Score(unittest.TestCase):
    def test_turn2_gain_and_move(self):
        got = {("m", "t1", CELL["question_id_a"]): 0.5, ("m", "t2", CELL["question_id_a"] + "|" + CELL["question_id_b"]): 0.6}
        (r,) = score([CELL], got, ["m", "absent"])
        self.assertAlmostEqual(r["excess_t2"], 0.01)
        self.assertAlmostEqual(r["stay"], 0.04)
        self.assertAlmostEqual(r["gain"], 0.03)
        self.assertAlmostEqual(r["move"], 0.1)
        self.assertAlmostEqual(r["target"], 0.3)


class Independence(unittest.TestCase):
    def test_base_rate_of_a_in_other_cities(self):
        items = [dict(world="kyoto", h="5y", qid="A7", q=0.9), dict(world="kyoto", h="5y", qid="A7", q=0.8),
                 dict(world="bruce", h="5y", qid="A7", q=0.2), dict(world="haight", h="5y", qid="A7", q=0.4),
                 dict(world="bruce", h="3y", qid="A7", q=0.0)]
        self.assertAlmostEqual(independence([CELL], items)[0], 0.3)  # kyoto's own snapshots left out


if __name__ == "__main__":
    unittest.main()
