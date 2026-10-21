"""Table of the latent skill theta and each model's rank on every cell of the combined score.
Rank 1 is the lowest loss; ties share the average rank. The combined rank ranks the mean of a model's
cell ranks, over the cells it has. Also writes the Spearman correlations between theta and every cell, and
between every pair of cells, to rank_correlation_table.tex. Standard library only:
    python3 make_rank_table.py --paper-root PAPER
"""
import argparse, csv, json
from datetime import date
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--paper-root", type=Path, required=True)
DATA = ap.parse_args().paper_root.resolve() / "data"
OUT = DATA / "rank_table.tex"
NAMES = {r["model"]: r["short_name"] for r in csv.DictReader(open(DATA / "model_names.csv"))}
THETA = json.load(open(DATA / "combined_score.json"))["theta"]
if set(NAMES.values()) != set(THETA):
    raise ValueError("model_names.csv does not match the models in combined_score.json")

# (simulation, two-line column header, file, loss column, row filter)
MICRO, FREE, STAR = "micropolis/micropolis_model_scores.csv", "freeciv/freeciv_results_wide.csv", "starsim/starsim_excess_long.csv"
def star(qtype, cond, rung):
    return lambda r: r["horizon"] == "pooled" and (r["question_type"], r["condition"], r["rung"]) == (qtype, cond, rung)
CELLS = [
    ("Micropolis", ("Mid-", "range"), MICRO, "mid_range_excess_brier", None),
    ("Micropolis", ("", "Tail"), MICRO, "tail_excess_bits", None),
    ("Micropolis", ("", "Cont."), MICRO, "excess_ncrps", None),
    ("FreeCiv", ("Mid-", "range"), FREE, "bank_all_excess_brier", None),
    ("FreeCiv", ("", "Tail"), FREE, "tails_all_excess_bits", None),
    ("FreeCiv", ("", "Cont."), FREE, "continuous_all_excess_ncrps_global", None),
    ("FreeCiv", ("Nat.", "cond."), FREE, "natcond_all_excess_t2", None),
    ("Starsim", ("", "Cont."), STAR, "excess", star("continuous", "unconditional", "-")),
    ("Starsim", ("", "Interv."), STAR, "excess", star("continuous", "interventional", "pooled(c25,c50,c90)")),
]

def load(path, col, keep):
    """Loss per short model name; None where the value is missing or the Starsim set is incomplete."""
    out = {}
    for r in csv.DictReader(open(DATA / path)):
        if keep and not keep(r):
            continue
        name = NAMES[r["model"]]
        if name in out:
            raise ValueError(f"Duplicate row for {name} in {path}")
        ok = r[col] != "" and r.get("complete", "True") == "True"
        out[name] = float(r[col]) if ok else None
    if set(out) != set(THETA):
        raise ValueError(f"Model set in {path} does not match combined_score.json")
    return out

def rank(values):
    """Average ranks, 1 = smallest; None stays None."""
    present = sorted((v, m) for m, v in values.items() if v is not None)
    out, i = {m: None for m in values}, 0
    while i < len(present):
        j = i
        while j + 1 < len(present) and present[j + 1][0] == present[i][0]:
            j += 1
        for k in range(i, j + 1):
            out[present[k][1]] = (i + j) / 2 + 1
        i = j + 1
    return out

ranks = [rank(load(path, col, keep)) for _, _, path, col, keep in CELLS]
mean_rank = {m: sum(r[m] for r in ranks if r[m] is not None) / sum(r[m] is not None for r in ranks) for m in THETA}
combined = rank(mean_rank)
models = sorted(THETA, key=THETA.get, reverse=True)

def write_if_changed(path, lines):
    """Write only when something other than the dated first line changes, so a rerun from .latexmkrc
    leaves the file, and latexmk's change detection, alone."""
    text = "\n".join(lines)
    old = path.read_text() if path.exists() else ""
    if old.split("\n", 1)[1:] == text.split("\n", 1)[1:]:
        return
    path.write_text(text)
    print(f"wrote {path}")

def fmt_rank(x):
    return "--" if x is None else (f"{x:.0f}" if x == int(x) else f"{x:.1f}")
def bold(s):
    return f"\\textbf{{{s}}}"
def fmt_theta(x):
    return f"{{\\boldmath${x:+.2f}$}}"
# Cell background runs through the seven-class PRGn scale, dark green (best) through white to dark purple (worst);
# text turns white on the darkest cells.
GRADIENT = [(27, 120, 55), (90, 174, 97), (166, 219, 160), (247, 247, 247), (194, 165, 207), (153, 112, 171), (118, 42, 131)]
def shade(s, t):
    """Shade the cell of s by t in [0, 1], 0 = best."""
    n = len(GRADIENT) - 1; seg = min(int(t * n), n - 1); u = t * n - seg
    rgb = [round(a + (b - a) * u) for a, b in zip(GRADIENT[seg], GRADIENT[seg + 1])]
    luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    text = f"\\color{{white}}{s}" if luminance < 120 else s
    return f"\\cellcolor[RGB]{{{','.join(map(str, rgb))}}}{text}"
def rank_shade(s, x, col):
    present = [v for v in col.values() if v is not None]
    return s if x is None else shade(s, (x - min(present)) / (max(present) - min(present)))

best_theta = max(THETA.values())
cols = [combined] + ranks
groups = [("Micropolis", 3), ("FreeCiv", 4), ("Starsim", 2)]
lines = [
    f"% Generated by data/scripts/make_rank_table.py ({date.today().isoformat()}); do not edit by hand.",
    "% theta: latent skill from data/combined_score.json. Ranks: 1 = lowest loss, ties share the average rank.",
    "% Cell background runs green (best) through white to purple (worst) within each column, linear in theta or in rank.",
    "% Losses: Micropolis from data/micropolis/micropolis_model_scores.csv; FreeCiv from data/freeciv/freeciv_results_wide.csv"
    " (bank_all_excess_brier, tails_all_excess_bits, continuous_all_excess_ncrps_global, natcond_all_excess_t2);"
    " Starsim from data/starsim/starsim_excess_long.csv (pooled horizon, excess). Names from data/model_names.csv.",
    "\\setlength{\\tabcolsep}{3pt}",
    "\\begin{tabular}{@{}l r r " + " ".join("r" * n for _, n in groups) + "@{}}",
    "\\toprule",
    " & & & " + " & ".join(f"\\multicolumn{{{n}}}{{c}}{{{g}}}" for g, n in groups) + " \\\\",
    "\\cmidrule(lr){4-6}\\cmidrule(lr){7-10}\\cmidrule(l){11-12}",
    " & & Avg & " + " & ".join(h[0] for _, h, *_ in CELLS) + " \\\\",
    "Model & $\\theta$ & Rank & " + " & ".join(h[1] for _, h, *_ in CELLS) + " \\\\",
    "\\midrule",
]
for m in models:
    lo, hi = min(THETA.values()), best_theta
    cells = [shade(bold(fmt_theta(THETA[m])), (hi - THETA[m]) / (hi - lo))]
    cells += [rank_shade(bold(fmt_rank(c[m])), c[m], c) for c in cols]
    lines.append(f"{m} & " + " & ".join(cells) + " \\\\")
lines += ["\\bottomrule", "\\end{tabular}", ""]
write_if_changed(OUT, lines)

# ---------------------------------------------------------------- Spearman correlations between theta and the cells
def spearman(a, b):
    """Spearman correlation over the models that have both values, re-ranked within that subset."""
    both = [m for m in THETA if a[m] is not None and b[m] is not None]
    ra, rb = rank({m: a[m] for m in both}), rank({m: b[m] for m in both})
    xa, xb = [ra[m] for m in both], [rb[m] for m in both]
    ma, mb = sum(xa) / len(xa), sum(xb) / len(xb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(xa, xb))
    return cov / (sum((x - ma) ** 2 for x in xa) * sum((y - mb) ** 2 for y in xb)) ** 0.5

ROW_LABELS = ["$\\theta_m$"] + [f"{sim} {label}" for (sim, *_), label in zip(CELLS, [
    "mid-range", "tail", "cont.", "mid-range", "tail", "cont.", "nat.\\ cond.", "cont.", "interv."])]
series = [rank({m: -v for m, v in THETA.items()})] + ranks  # all as ranks with 1 = best, so a positive correlation means agreement
CORR_OUT = DATA / "rank_correlation_table.tex"
lines = [
    f"% Generated by data/scripts/make_rank_table.py ({date.today().isoformat()}); do not edit by hand.",
    "% Spearman correlation between the ranks of the models on theta and on each cell, 1 = best in every series,",
    "% so a positive value means the two agree. Pairs with the Starsim interventional cell use the 23 models that have it.",
    "% Cell background runs green (+1) through white (0) to purple (-1). Inputs as in data/rank_table.tex.",
    "\\setlength{\\tabcolsep}{3pt}",
    "\\begin{tabular}{@{}l r " + " ".join("r" * n for _, n in groups) + "@{}}",
    "\\toprule",
    " & & " + " & ".join(f"\\multicolumn{{{n}}}{{c}}{{{g}}}" for g, n in groups) + " \\\\",
    "\\cmidrule(lr){3-5}\\cmidrule(lr){6-9}\\cmidrule(l){10-11}",
    " & & " + " & ".join(h[0] for _, h, *_ in CELLS) + " \\\\",
    " & $\\theta_m$ & " + " & ".join(h[1] for _, h, *_ in CELLS) + " \\\\",
    "\\midrule",
]
for i, (label, a) in enumerate(zip(ROW_LABELS, series)):
    cells = []
    for j, b in enumerate(series):
        if i == j:
            cells.append("")
            continue
        r = spearman(a, b)
        cells.append(shade(bold(f"{{\\boldmath${r:.2f}$}}".replace("0.", ".")), (1 - r) / 2))  # no leading zero, to fit
    lines.append(f"{label} & " + " & ".join(cells) + " \\\\")
    if i == 0:
        lines.append("\\midrule")
lines += ["\\bottomrule", "\\end{tabular}", ""]
write_if_changed(CORR_OUT, lines)
