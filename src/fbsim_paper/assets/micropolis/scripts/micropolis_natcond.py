#!/usr/bin/env python3
"""The Micropolis natural conditionals: figure, appendix table, macros and per-model scores.

Reads the draw and the model answers (the data archive's datasets/micropolis-natcond), and from the gathered
paper data the binary questions (for the independence baseline) and model_scores.csv (for ECI). Scores each
model on the cells it answered at both turns, as FreeCiv's score_v2.py does (fbsim_paper.natcond); a cell a
model left unanswered is left out of that model's means, and every output reports the coverage. The helpers
here are shared with micropolis_intcond.py.

Writes into the manuscript checkout:

- figures/fig_micropolis_natcond.pdf: (a) turn-2 excess Brier against ECI, with independence; (b) model move
  p2 - p1 against the true shift P(A|B) - P(A), as FreeCiv's fig_freeciv_natcond_update.pdf;
- data/appendix_tables/micropolis_natcond_blocks.tex: per model, turn-2 excess Brier and gain by block;
- data/micropolis_natcond_macros.tex: \\MPNC* macros for the prose;
- data/micropolis/micropolis_natcond_scores.csv and micropolis_natcond_summary.json: the numbers behind them.

Usage:
    scripts/micropolis_natcond.py --natcond DIR --datadir DIR --model-names CSV --paper-root DIR
"""

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from fbsim_paper import capability_plot as cp
from fbsim_paper.natcond import answers, independence, score

sys.path.insert(0, str(Path(__file__).parent))
from analyze_continuous import bootstrap_rho_ci
from gather_paper_data import BINARY_CSV_NAME

BLOCKS = ["irrelevant", "mechanical", "inferential"]
BIG_SHIFT = 0.05  # |true shift| at or above which the direction of the update is checked, as FreeCiv


def read_jsonl(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as f:
        return [json.loads(line) for line in f]


def binary_items(datadir):
    items = {}
    with open(datadir / BINARY_CSV_NAME) as f:
        for r in csv.DictReader(f):
            items[r["question_id"]] = dict(world=r["question_id"].split("_")[0], h=r["horizon"], qid=r["qid"],
                                           q=float(r["real_prob"]))
    return list(items.values())


def eci_by_slug(datadir):
    with open(datadir / "model_scores.csv") as f:
        return {r["slug"]: float(r["ECI"]) for r in csv.DictReader(f)}


def short_names(path):
    with open(path) as f:
        return {r["model"]: r["short_name"] for r in csv.DictReader(f)}


def fmt(x, dp=3):
    return "--" if x is None or np.isnan(x) else f"{x:.{dp}f}".replace("-", "$-$")


def num(v, dp=3):
    return f"{v:.{dp}f}"


def below(x, base, dp=3):
    """A table cell, bold when below the baseline's score."""
    return f"\\textbf{{{fmt(x, dp)}}}" if base is not None and x < base else fmt(x, dp)


def parse_args(doc, study):
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(f"--{study}", type=Path, required=True, help=f"the data archive's datasets/micropolis-{study}")
    ap.add_argument("--datadir", type=Path, required=True, help="the gathered paper data (paper-inputs/micropolis)")
    ap.add_argument("--model-names", type=Path, required=True, help="paper-inputs/model_names.csv")
    ap.add_argument("--paper-root", type=Path, required=True)
    return ap.parse_args()


def load(results, datadir, model_names, cells, last=False):
    """Models (best ECI first), ECI, short names, the scored records and those records by model."""
    rows = read_jsonl(results)
    for r in rows:  # the registry's ":loeff" suffix is not part of the model id
        r["model"] = r["model"].split(":")[0]
    eci, short = eci_by_slug(datadir), short_names(model_names)
    models = sorted({r["model"] for r in rows}, key=lambda m: -eci[m])
    scored = score(cells, answers(rows, last=last), models)
    by_model = defaultdict(list)
    for s in scored:
        by_model[s["model"]].append(s)
    return models, eci, short, scored, by_model


def baselines(cells, datadir, blocks):
    """Independence (A's base rate) and the true P(A), both ignoring the condition: their means, per-cell scores
    and the cells' blocks."""
    rate = independence(cells, binary_items(datadir))
    qg = np.array([c["p_a_given_b"] for c in cells])
    blk = np.array([c["block"] for c in cells])
    indep = (rate - qg) ** 2
    true_p = (np.array([c["p_a"] for c in cells]) - qg) ** 2
    base = dict(independence=float(indep.mean()), true_p=float(true_p.mean()),
                independence_by_block={b: float(indep[blk == b].mean()) for b in blocks})
    return base, indep, true_p, blk


def per_model(s, eci, blocks, block_keys=("excess_t2", "gain"), **extra):
    """One model's means over its scored records `s`, overall and by block; `extra` goes before by_block."""
    big = [x for x in s if abs(x["target"]) >= BIG_SHIFT]
    return dict(
        eci=eci, n_cells=len(s),
        excess_t2=float(np.mean([x["excess_t2"] for x in s])), stay=float(np.mean([x["stay"] for x in s])),
        gain=float(np.mean([x["gain"] for x in s])),
        pearson_move_target=float(stats.pearsonr([x["move"] for x in s], [x["target"] for x in s]).statistic),
        direction_correct=float(np.mean([np.sign(x["move"]) == np.sign(x["target"]) for x in big])), n_big=len(big),
        **extra,
        by_block={b: dict(n=sum(x["block"] == b for x in s),
                          **{k: float(np.mean([x[k] for x in s if x["block"] == b])) for k in block_keys})
                  for b in blocks})


def capability(models, per):
    """ECI and turn-2 excess per model, and the sign-adjusted Spearman rho with its p-value and model bootstrap."""
    x = np.array([per[m]["eci"] for m in models])
    y = np.array([per[m]["excess_t2"] for m in models])
    rho, rho_p = stats.spearmanr(x, -y)  # sign-adjusted: positive means more capable models score better
    return x, y, rho, rho_p, bootstrap_rho_ci(list(x), list(-y))


def cell_update(scored, cells):
    """Per cell, the true shift and the mean move over the models that answered it, with their r and OLS slope."""
    cell_moves = defaultdict(list)
    for s in scored:
        cell_moves[s["cell"]].append(s["move"])
    target = {c["cell_id"]: c["p_a_given_b"] - c["p_a"] for c in cells}
    cid = sorted(cell_moves)
    ct, cm = np.array([target[c] for c in cid]), np.array([np.mean(cell_moves[c]) for c in cid])
    return dict(target=target, n=len(cid), ct=ct, cm=cm, r=float(stats.pearsonr(cm, ct).statistic),
                slope=float(np.polyfit(ct, cm, 1)[0]))


def summarize(cells, models, scored, per, y, rho, rho_p, rho_ci, base, upd, after_blocks=None, after_baselines=None):
    """The summary JSON's content; `after_blocks` and `after_baselines` are study-specific entries."""
    target = upd["target"]
    return dict(
        n_cells=len(cells), n_models=len(models), n_pairs=len(scored),
        cells_per_model=[min(p["n_cells"] for p in per.values()), max(p["n_cells"] for p in per.values())],
        blocks=dict(Counter(c["block"] for c in cells)), **(after_blocks or {}),
        mean_excess_t2=float(y.mean()), rho=float(rho), rho_p=float(rho_p), rho_ci_models=rho_ci,
        gain_mean=float(np.mean([p["gain"] for p in per.values()])),
        gain_positive_models=int(sum(p["gain"] > 0 for p in per.values())),
        direction_correct_range=[min(p["direction_correct"] for p in per.values()),
                                 max(p["direction_correct"] for p in per.values())],
        big_shift_cells=int(sum(abs(target[c]) >= BIG_SHIFT for c in target)),
        beat_independence=int(sum(p["excess_t2"] < base["independence"] for p in per.values())),
        baselines=base, **(after_baselines or {}),
        cells_update=dict(n=upd["n"], pearson=upd["r"], ols_slope=upd["slope"],
                          mean_abs_move=float(np.abs(upd["cm"]).mean()), mean_abs_target=float(np.abs(upd["ct"]).mean())),
        per_model=per)


def write_tables(paper, study, cells, models, per, short, summary, blocks, labels, block_keys=("excess_t2", "gain"),
                 extra_cols=()):
    """The summary JSON, the per-model scores CSV and the appendix table of excess and gain by block."""
    (paper / "data/micropolis").mkdir(parents=True, exist_ok=True)
    (paper / f"data/micropolis/micropolis_{study}_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    with open(paper / f"data/micropolis/micropolis_{study}_scores.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "eci", "n_cells", "excess_t2", "stay", "gain"] + [c for c, _ in extra_cols]
                   + [f"{b}_{k}" for b in blocks for k in ("n", *block_keys)])
        for m in models:
            p = per[m]
            w.writerow([m, p["eci"], p["n_cells"], p["excess_t2"], p["stay"], p["gain"]] + [p[k] for _, k in extra_cols]
                       + [p["by_block"][b][k] for b in blocks for k in ("n", *block_keys)])

    n, base = len(blocks), summary["baselines"]
    lines = [f"% Generated by forecastbench-sim-paper/src/fbsim_paper/assets/micropolis/scripts/micropolis_{study}.py "
             f"from datasets/micropolis-{study}; do not edit by hand.",
             f"% Coverage: models answered {summary['cells_per_model'][0]}-{summary['cells_per_model'][1]} of the "
             f"{len(cells)} cells at both turns.",
             "\\setlength{\\tabcolsep}{3pt}", f"\\begin{{tabular}}{{l{'r' * (2 + 2 * n)}}}", "\\toprule",
             f"Model & ECI & Cells & \\multicolumn{{{n}}}{{c}}{{Turn-2 excess Brier, by block}} & "
             f"\\multicolumn{{{n}}}{{c}}{{Gain over not updating, by block}} \\\\",
             f"\\cmidrule(lr){{4-{3 + n}}}\\cmidrule(lr){{{4 + n}-{3 + 2 * n}}}",
             " & & & " + " & ".join(labels + labels) + " \\\\", "\\midrule"]
    for m in models:
        p = per[m]
        lines.append(" & ".join([short.get(m, m), f"{p['eci']:.1f}", str(p["n_cells"])]
                                + [below(p["by_block"][b]["excess_t2"], base["independence_by_block"][b]) for b in blocks]
                                + [fmt(p["by_block"][b]["gain"]) for b in blocks]) + " \\\\")
    lines.append("\\midrule Independence & & " + str(len(cells)) + " & "
                 + " & ".join(fmt(base["independence_by_block"][b]) for b in blocks) + " &" * n + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (paper / "data/appendix_tables").mkdir(parents=True, exist_ok=True)
    (paper / f"data/appendix_tables/micropolis_{study}_blocks.tex").write_text("\n".join(lines) + "\n")


def core_macros(cells, models, scored, summary, rho_ci, after_cells=None):
    """The macros both studies share, in the order they are written; `after_cells` are study-specific."""
    upd, base = summary["cells_update"], summary["baselines"]
    return dict(
        NCells=str(len(cells)), NModels=str(len(models)), NPairs=f"{len(scored):,}",
        CellsMin=str(summary["cells_per_model"][0]), CellsMax=str(summary["cells_per_model"][1]), **(after_cells or {}),
        MeanExcess=num(summary["mean_excess_t2"]), Rho=num(summary["rho"], 2),
        RhoLo=num(rho_ci[0], 2) if rho_ci else "--", RhoHi=num(rho_ci[1], 2) if rho_ci else "--",
        GainMean=num(summary["gain_mean"]), GainPositive=str(summary["gain_positive_models"]),
        DirLo=f"{100 * summary['direction_correct_range'][0]:.0f}", DirHi=f"{100 * summary['direction_correct_range'][1]:.0f}",
        BigShiftCells=str(summary["big_shift_cells"]),
        Independence=num(base["independence"]), TrueP=num(base["true_p"]), BeatIndependence=str(summary["beat_independence"]),
        CellR=num(upd["pearson"], 2), CellSlope=num(upd["ols_slope"], 2),
        MeanAbsMove=num(upd["mean_abs_move"], 2), MeanAbsShift=num(upd["mean_abs_target"], 2),
        MoveShiftRatio=num(upd["mean_abs_move"] / upd["mean_abs_target"], 1),
        NUnanswered=str(len(models) * len(cells) - len(scored)))


def write_macros(paper, study, prefix, cells, summary, macros):
    text = [f"% Generated by forecastbench-sim-paper/src/fbsim_paper/assets/micropolis/scripts/micropolis_{study}.py; "
            "do not edit by hand.",
            f"% Coverage: models answered {summary['cells_per_model'][0]}-{summary['cells_per_model'][1]} of the "
            f"{len(cells)} cells at both turns (see micropolis_{study}_summary.json)."]
    text += [f"\\newcommand{{\\{prefix}{k}}}{{{v}}}" for k, v in macros.items()]
    (paper / f"data/micropolis_{study}_macros.tex").write_text("\n".join(text) + "\n")


def write_figure(paper, study, x, y, rho, rho_ci, base, scored, upd, title_a, shift_label):
    """(a) turn-2 excess Brier against ECI, with independence; (b) model move against the true shift."""
    ct, cm = upd["ct"], upd["cm"]
    with cp.style():
        fig, (ax1, ax2) = cp.figure(2)
        cp.draw_panel(ax1, x, y, cp.rho_note(rho, rho_ci), "Turn-2 excess Brier\n(lower is better)",
                      title_a, reference=base["independence"])
        lim = max(0.3, float(np.ceil(10 * max(np.abs(ct).max(), np.abs(cm).max())) / 10))
        ax2.axhline(0, color="0.85", lw=0.5, zorder=1)
        ax2.axvline(0, color="0.85", lw=0.5, zorder=1)
        ax2.plot([-lim, lim], [-lim, lim], color="0.5", ls="--", lw=0.7, zorder=2)
        # rasterized: thousands of vector markers exhaust TeX's memory under the pgf backend
        ax2.scatter([s["target"] for s in scored], [s["move"] for s in scored], s=1.5, color="0.8", linewidths=0,
                    zorder=2, rasterized=True)
        ax2.scatter(ct, cm, s=5, color=cp.POINT_COLOR, linewidths=0, zorder=3)
        ax2.set_xlim(-lim, lim)
        ax2.set_ylim(-lim, lim)
        ax2.set_xlabel(f"True shift ${shift_label} - P(A)$")
        ax2.set_ylabel("Move $p_2 - p_1$")
        ax2.set_title("(b) Update against the true shift", loc="left", fontsize=7)
        ax2.text(0.03, 0.955, f"cells: $r = {upd['r']:.2f}$, slope ${upd['slope']:.2f}$", transform=ax2.transAxes,
                 fontsize=6, color=cp.POINT_COLOR, va="top", ha="left")
        ax2.spines[["top", "right"]].set_visible(False)
        (paper / "figures").mkdir(exist_ok=True)
        cp.save(fig, paper / f"figures/fig_micropolis_{study}.pdf")


def report(study, models, scored, summary, rho_ci):
    upd, base = summary["cells_update"], summary["baselines"]
    print(f"{study}: {len(models)} models, {len(scored):,} model-cell pairs ({summary['cells_per_model'][0]}-"
          f"{summary['cells_per_model'][1]} cells per model); mean turn-2 excess {summary['mean_excess_t2']:.4f}, "
          f"rho {summary['rho']:+.2f} {rho_ci}; independence {base['independence']:.4f}, true P(A) {base['true_p']:.4f}; "
          f"cells r {upd['pearson']:.2f} slope {upd['ols_slope']:.2f}")


def main():
    args = parse_args(__doc__, "natcond")
    cells = read_jsonl(args.natcond / "natcond_400_seed42.jsonl")
    models, eci, short, scored, by_model = load(args.natcond / "results.jsonl.gz", args.datadir, args.model_names, cells)
    base, indep, _, blocks = baselines(cells, args.datadir, BLOCKS)
    per = {m: per_model(by_model[m], eci[m], BLOCKS) for m in models}
    x, y, rho, rho_p, rho_ci = capability(models, per)

    # the same without the mechanical group, the one where updating helps, for comparisons with FreeCiv's mix
    nomech = [b for b in BLOCKS if b != "mechanical"]
    y_nm = np.array([np.mean([s["excess_t2"] for s in by_model[m] if s["block"] in nomech]) for m in models])
    ind_nm = float(indep[np.isin(blocks, nomech)].mean())
    rho_nm = float(stats.spearmanr(x, -y_nm).statistic)
    rho_nm_ci = bootstrap_rho_ci(list(x), list(-y_nm))
    no_mechanical = dict(n_cells=int(np.isin(blocks, nomech).sum()), rho=rho_nm, rho_ci_models=rho_nm_ci,
                         independence=ind_nm, beat_independence=int((y_nm < ind_nm).sum()))

    upd = cell_update(scored, cells)
    summary = summarize(cells, models, scored, per, y, rho, rho_p, rho_ci, base, upd,
                        after_baselines=dict(no_mechanical=no_mechanical))
    paper = args.paper_root
    write_tables(paper, "natcond", cells, models, per, short, summary, BLOCKS, ["Irrel.", "Mech.", "Infer."])

    counts = summary["blocks"]
    macros = core_macros(cells, models, scored, summary, rho_ci, after_cells=dict(
        NIrrelevant=str(counts.get("irrelevant", 0)), NMechanical=str(counts.get("mechanical", 0)),
        NInferential=str(counts.get("inferential", 0))))
    macros.update(
        NoMechCells=str(no_mechanical["n_cells"]), NoMechRho=num(rho_nm, 2),
        NoMechRhoLo=num(rho_nm_ci[0], 2) if rho_nm_ci else "--", NoMechRhoHi=num(rho_nm_ci[1], 2) if rho_nm_ci else "--",
        NoMechIndependence=num(ind_nm), NoMechBeatIndependence=str(no_mechanical["beat_independence"]))
    # by block: mean gain over models, models with negative gain, independence, models scoring below it
    for b, name in zip(BLOCKS, ["Irrelevant", "Mechanical", "Inferential"]):
        gains = [per[m]["by_block"][b]["gain"] for m in models]
        excess = [per[m]["by_block"][b]["excess_t2"] for m in models]
        ind = base["independence_by_block"][b]
        macros[f"Gain{name}"] = num(float(np.mean(gains)))  # signed: use in math mode
        macros[f"GainNeg{name}"] = str(sum(g < 0 for g in gains))
        macros[f"Indep{name}"] = num(ind)
        macros[f"BelowIndep{name}"] = str(sum(e < ind for e in excess))
    write_macros(paper, "natcond", "MPNC", cells, summary, macros)

    write_figure(paper, "natcond", x, y, rho, rho_ci, base, scored, upd, "(a) Excess Brier after the reveal",
                 "P(A \\mid B)")
    report("natcond", models, scored, summary, rho_ci)


if __name__ == "__main__":
    main()
