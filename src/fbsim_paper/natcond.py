"""Scoring of natural-conditional cells, as FreeCiv's score_v2.py defines it.

A cell asks question A twice: p1 at turn 1, p2 at turn 2 after one revealed fact B. Its truth is
q = P(A) and q_given = P(A | B), frequencies over the replays.

- excess_t2 = (p2 - q_given)^2, the headline;
- stay = (p1 - q_given)^2, the score of not updating; gain = stay - excess_t2;
- move = p2 - p1, against the true shift target = q_given - q.
"""

import numpy as np

from fbsim_paper.baselines import base_rates


def answers(rows, last=False):
    """Each (model, arm, item)'s answer: the value of its first row with a parsed value, or its last with `last`
    (for results where a later row supersedes an earlier one)."""
    out = {}
    for r in rows:
        k = (r["model"], r["arm"], r["item"])
        if r["value"] is not None and (last or k not in out):
            out[k] = float(r["value"])
    return out


def score(cells, answered, models):
    """One record per (model, cell) that has both turns answered."""
    out = []
    for c in cells:
        qa, item2 = c["question_id_a"], f"{c['question_id_a']}|{c['question_id_b']}"
        q, qg = c["p_a"], c["p_a_given_b"]
        for m in models:
            p1, p2 = answered.get((m, "t1", qa)), answered.get((m, "t2", item2))
            if p1 is None or p2 is None:
                continue
            stay, excess = (p1 - qg) ** 2, (p2 - qg) ** 2
            out.append(dict(model=m, cell=c["cell_id"], block=c["block"], p1=p1, p2=p2, q=q, q_given=qg,
                            excess_t2=excess, stay=stay, gain=stay - excess, move=p2 - p1, target=qg - q))
    return out


def independence(cells, binary_items):
    """Each cell's independence forecast: question A's base rate, as micropolis_baselines.py computes it (the
    mean q of the same template at the same horizon in the other cities, both snapshots), whatever fact is
    revealed. `binary_items` are the binary set's questions (world = city, h = "3y".., qid, q)."""
    keys = [lambda it: (it["h"], it["qid"]), lambda it: it["qid"]]
    rate = {(it["world"], it["h"], it["qid"]): r for it, r in zip(binary_items, base_rates(binary_items, keys))}
    return np.array([rate[c["city"], f"{c['horizon_a'] // 48}y", c["qid_a"]] for c in cells])
