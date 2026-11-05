#!/usr/bin/env python3
"""The Micropolis interventional conditionals: figure, appendix table, macros and per-model scores.

As micropolis_natcond.py, with an intervention X done once right after the snapshot in place of the revealed fact:
the target is P(A | do X), the frequency of A over 1,000 continuations with X, against P(A) over 1,000 without.
Reads the draw and the model answers (the data archive's datasets/micropolis-intcond), whose results take each
key's last parsed row (a later row supersedes an earlier one there; see its README).

Writes into the manuscript checkout:

- figures/fig_micropolis_intcond.pdf: (a) turn-2 excess Brier against ECI, with independence; (b) model move
  p2 - p1 against the true shift P(A | do X) - P(A);
- data/appendix_tables/micropolis_intcond_blocks.tex: per model, turn-2 excess Brier and gain by block;
- data/micropolis_intcond_macros.tex: \\MPIC* macros for the prose;
- data/micropolis/micropolis_intcond_scores.csv and micropolis_intcond_summary.json: the numbers behind them.

Usage:
    scripts/micropolis_intcond.py --intcond DIR --datadir DIR --model-names CSV --paper-root DIR
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from micropolis_natcond import (baselines, capability, cell_update, core_macros, load, num, parse_args, per_model,
                                read_jsonl, report, summarize, write_figure, write_macros, write_tables)

BLOCKS = ["null", "same-family", "damage", "infrastructure"]
NAMES = dict(zip(BLOCKS, ["Null", "Same", "Damage", "Infra"]))  # macro suffixes
SAME_HIGH = 0.9  # a same-family turn-2 forecast at or above this counts the forced disaster itself
SAME_HIGH_CELLS = 5  # a model doing so on at least this many same-family cells is counted


def as_natcond(c):
    """The cell in natural-conditional form, so that fbsim_paper.natcond scores it: B is "do-<action>"."""
    return dict(cell_id=c["cell_id"], block=c["block"], action=c["action"], city=c["city"], horizon_a=c["horizon"],
                qid_a=c["qid"], question_id_a=c["question_id"], question_id_b=f"do-{c['action']}",
                p_a=c["p_a"], p_a_given_b=c["p_a_do"])


def main():
    args = parse_args(__doc__, "intcond")
    cells = [as_natcond(c) for c in read_jsonl(args.intcond / "intcond_400_seed42.jsonl")]
    models, eci, short, scored, by_model = load(args.intcond / "results.jsonl.gz", args.datadir, args.model_names,
                                                cells, last=True)
    base, _, true_p, blocks = baselines(cells, args.datadir, BLOCKS)
    base["true_p_by_block"] = {b: float(true_p[blocks == b].mean()) for b in BLOCKS}
    keys = ("excess_t2", "gain", "move")
    per = {m: per_model(by_model[m], eci[m], BLOCKS, keys, same_high=int(sum(
               x["p2"] >= SAME_HIGH for x in by_model[m] if x["block"] == "same-family"))) for m in models}
    x, y, rho, rho_p, rho_ci = capability(models, per)
    upd = cell_update(scored, cells)
    summary = summarize(cells, models, scored, per, y, rho, rho_p, rho_ci, base, upd,
                        after_blocks=dict(actions=dict(Counter(c["action"] for c in cells))))
    paper = args.paper_root
    write_tables(paper, "intcond", cells, models, per, short, summary, BLOCKS, ["Null", "Same", "Dam.", "Infra."],
                 keys, extra_cols=[("same_family_high", "same_high")])

    same_high = {m: per[m]["same_high"] for m in models}
    best = min(models, key=lambda m: per[m]["excess_t2"])
    worst_same = max(same_high, key=same_high.get)
    macros = core_macros(cells, models, scored, summary, rho_ci)
    macros.update(
        NActions=str(len(summary["actions"])),
        BestExcess=num(per[best]["excess_t2"]), BestModel=short.get(best, best),
        SameHighModels=str(sum(v >= SAME_HIGH_CELLS for v in same_high.values())),
        SameHighMax=str(max(same_high.values())), SameHighMaxModel=short.get(worst_same, worst_same))
    # by block: cells, mean gain over models, models with negative gain, independence, models scoring below it
    for b in BLOCKS:
        name = NAMES[b]
        gains = [per[m]["by_block"][b]["gain"] for m in models]
        excess = [per[m]["by_block"][b]["excess_t2"] for m in models]
        ind = base["independence_by_block"][b]
        macros[f"N{name}"] = str(summary["blocks"].get(b, 0))
        macros[f"Gain{name}"] = num(float(np.mean(gains)))  # signed: use in math mode
        macros[f"GainNeg{name}"] = str(sum(g < 0 for g in gains))
        macros[f"Indep{name}"] = num(ind)
        macros[f"TrueP{name}"] = num(base["true_p_by_block"][b])
        macros[f"BelowIndep{name}"] = str(sum(e < ind for e in excess))
        macros[f"Move{name}"] = num(float(np.mean([per[m]["by_block"][b]["move"] for m in models])))  # signed
    write_macros(paper, "intcond", "MPIC", cells, summary, macros)

    write_figure(paper, "intcond", x, y, rho, rho_ci, base, scored, upd, "(a) Excess Brier under the intervention",
                 "P(A \\mid \\mathrm{do}\\,X)")
    report("intcond", models, scored, summary, rho_ci)


if __name__ == "__main__":
    main()
