#!/usr/bin/env python
"""Edit the FreeCiv cells of the tables that three worlds share, in place.

    python src/fbsim_paper/assets/freeciv/update_shared_tables.py [--final] [--check]

Touches, FreeCiv cells only, leaving every other cell as it is:
  data/roster_table.tex                  the FreeCiv reasoning-setting column
  data/validation_table.tex              the four FreeCiv rows (rho vs ECI, CI over models, p, CI over the 8 games)
  data/validation_table_forecastbench.tex the same rows against ForecastBench overall
  data/validation_table_main.tex         the four FreeCiv rows with the eight-game interval as the one CI
and writes data/freeciv/freeciv_validation_stats.json with every statistic and its method.

Row and column positions are located by label, never by index alone, and the script refuses to write if a
table's shape is not what it expects.

--final drops the "(provisional)" qualifier from the FreeCiv row label and the comment lines (for the
rerun at 50 questions per prompt).  --check recomputes and reports differences without writing.

Sources (data/freeciv/): freeciv_results_wide.csv (headline scores, calls, cost), models_v1.csv (reasoning setting),
score_items.csv.gz (per-item rows for the cluster bootstrap over the eight anchor games), model_scores.csv.
The FreeCiv statistics reproduce the retired data/compute_validation_stats.py (same seed, same resample
count, same bootstrap order).
"""
import json
import re
import sys
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from _common import (DATA, MODELS_FILE, N_BOOT, RUN, PAPER_DATA, REPO, SCORE_ITEMS, SEED, WIDE,
                     display_name, load_capability, load_items, load_wide, tex, rel)

FINAL = "--final" in sys.argv[1:]
CHECK = "--check" in sys.argv[1:]

# The four FreeCiv headline rows: (table label, wide column, score_items set, score_items column).
FREECIV_SETS = [
    ("Excess nCRPS", "continuous_all_excess_ncrps_global", "continuous", "excess_ncrps_global"),
    ("Excess bits, tail", "tails_all_excess_bits", "tails", "excess_bits"),
    ("Excess Brier, natural conditional", "natcond_all_excess_t2", "natcond", "excess_t2"),
    ("Excess Brier, mid-range", "bank_all_excess_brier", "bank", "excess_brier"),
]
WORLD_LABEL = "FreeCiv" if FINAL else "\\shortstack[l]{FreeCiv\\\\(provisional)}"


def read_lines(path):
    return path.read_text().splitlines()


def write_lines(path, lines, old):
    new = "\n".join(lines) + "\n"
    if new == old:
        print(f"unchanged  {rel(path)}")
        return
    if CHECK:
        print(f"WOULD EDIT {rel(path)}")
        return
    path.write_text(new)
    print(f"edited     {rel(path)}")


def cells_of(line):
    body = line.rstrip()
    assert body.endswith("\\\\"), line
    return [c.strip() for c in body[:-2].split("&")]


def join_cells(cells):
    return " & ".join(cells) + " \\\\"


# ---------------------------------------------------------------- statistics
def spearman_stats(x, y, rng):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = len(x)
    rho, p = spearmanr(x, y)
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boots = np.empty(N_BOOT)
    for i in range(N_BOOT):
        boots[i] = spearmanr(x[idx[i]], y[idx[i]])[0]
    ok = ~np.isnan(boots)
    lo, hi = np.percentile(boots[ok], [2.5, 97.5])
    return dict(n=int(n), rho=float(rho), p=float(p), ci_lo=float(lo), ci_hi=float(hi), n_boot_valid=int(ok.sum()))


def cluster_tables(items):
    tabs = {}
    for label, wcol, iset, icol in FREECIV_SETS:
        sub = items[items["set"] == iset]
        g = sub.groupby(["model", "world"])[icol].agg(["sum", "count"])
        tabs[wcol] = dict(sum=g["sum"].unstack("world"), cnt=g["count"].unstack("world"),
                          items_per_world={w: int(n) for w, n in sub.groupby("world")["item"].nunique().items()})
    return tabs


def cluster_bootstrap(tab, cap_axis, sign, rng):
    S, C = tab["sum"], tab["cnt"]
    worlds, models = list(S.columns), list(S.index)
    axis = cap_axis.reindex(models)
    keep = axis.notna().values
    Sv, Cv, ax = S.values[keep], C.values[keep], axis.values[keep]
    empty = [m for m, c in zip(np.array(models)[keep], Cv.sum(1)) if c == 0]
    assert not empty, f"no scored items in this set for {empty}: the run is incomplete"
    k = len(worlds)
    boots = np.empty(N_BOOT)
    for i in range(N_BOOT):
        draw = rng.integers(0, k, size=k)
        mult = np.bincount(draw, minlength=k).astype(float)
        boots[i] = spearmanr(ax, sign * ((Sv @ mult) / (Cv @ mult)))[0]
    ok = ~np.isnan(boots)
    lo, hi = np.percentile(boots[ok], [2.5, 97.5])
    full = Sv.sum(1) / Cv.sum(1)
    return dict(ci_lo=float(lo), ci_hi=float(hi), n_boot_valid=int(ok.sum()), n_clusters=k, clusters=worlds,
                items_per_world=tab["items_per_world"], full_sample_means=dict(zip(np.array(models)[keep], map(float, full))))


def fmt_p(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def fmt_ci(lo, hi):
    return f"$[{lo:.2f}, {hi:.2f}]$"


def validation_rows():
    cap = load_capability()
    w = load_wide()
    items = load_items()
    tabs = cluster_tables(items)
    out = []
    for label, wcol, iset, icol in FREECIV_SETS:
        vals = w[wcol].dropna()
        vals = vals[vals.index.isin(cap.index)]
        rec = dict(score=label, column=wcol, items_set=iset, items_column=icol, lower_is_better=True,
                   per_model_score={m: float(v) for m, v in vals.sort_values().items()},
                   best_model=vals.idxmin(), best_score=float(vals.min()))
        for axis_key in ("eci", "fb"):
            ax = cap[axis_key].reindex(vals.index)
            keep = ax.notna()
            rng = np.random.default_rng(SEED)
            st = spearman_stats(ax[keep].values, -vals[keep].values, rng)
            st["models"] = sorted(vals.index[keep])
            rec[axis_key] = st
            rng = np.random.default_rng(SEED)
            cl = cluster_bootstrap(tabs[wcol], cap[axis_key], -1.0, rng)
            for m, v in cl["full_sample_means"].items():
                assert abs(v - float(vals[m])) < 1e-9, (wcol, m, v, vals[m])
            del cl["full_sample_means"]
            rec[f"{axis_key}_cluster"] = cl
        out.append(rec)
    return out


# ---------------------------------------------------------------- the tables
def update_validation(rows):
    def replace_block(path, make_cells):
        if not path.is_file():   # the manuscript reads hand-frozen copies since the 2026-09-24 code freeze
            return
        old = path.read_text()
        lines = read_lines(path)
        # locate the FreeCiv block: the row whose first cell holds a multirow with FreeCiv, plus the three rows after it
        start = next(i for i, l in enumerate(lines) if "multirow" in l and "FreeCiv" in l)
        block = lines[start:start + 4]
        assert all(l.rstrip().endswith("\\\\") for l in block), block
        OLD_LABELS = {"nCRPS": "Excess nCRPS", "Bank excess Brier": "Excess Brier, mid-range", "Mid-range excess Brier": "Excess Brier, mid-range",   # labels before 21 September 2026
                      "Tail excess bits": "Excess bits, tail", "Natural-conditional excess Brier": "Excess Brier, natural conditional"}
        assert [OLD_LABELS.get(cells_of(l)[1], cells_of(l)[1]) for l in block] == [r["score"] for r in rows], [cells_of(l)[1] for l in block]
        new_block = []
        for gi, r in enumerate(rows):
            cells = make_cells(r)
            cell_world = f"\\multirow{{4}}{{*}}{{{WORLD_LABEL}}}" if gi == 0 else ""
            new_block.append(join_cells([cell_world] + cells))
        lines[start:start + 4] = new_block
        if FINAL:
            lines = [re.sub(r"; FreeCiv is provisional \(one question per prompt\)", "", l) if l.startswith("%") else l for l in lines]
        lines = [l.replace("one CI column (models for Micropolis and StarSim; eight-game cluster bootstrap for FreeCiv)", "one CI column, the bootstrap over models in every row (Appendix C adds FreeCiv's interval over its eight worlds)") if l.startswith("%") else l for l in lines]
        write_lines(path, lines, old)

    def full(axis):
        def make(r):
            st, cl = r[axis], r[f"{axis}_cluster"]
            return [r["score"], str(st["n"]), f"${st['rho']:.2f}$", fmt_ci(st["ci_lo"], st["ci_hi"]), fmt_p(st["p"]),
                    fmt_ci(cl["ci_lo"], cl["ci_hi"])]
        return make

    def main_(r):
        st, cl = r["eci"], r["eci_cluster"]
        return [r["score"], str(st["n"]), f"${st['rho']:.2f}$", fmt_ci(st["ci_lo"], st["ci_hi"]), fmt_p(st["p"])]   # 21 September 2026: the interval over models, as in every other row

    replace_block(PAPER_DATA / "validation_table.tex", full("eci"))
    replace_block(PAPER_DATA / "validation_table_forecastbench.tex", full("fb"))
    replace_block(PAPER_DATA / "validation_table_main.tex", main_)


def freeciv_run_records():
    """Per model: display name and reasoning setting, from models_v1.csv."""
    fc = pd.read_csv(MODELS_FILE)
    assert len(fc) == 24, len(fc)
    fc["dname"] = fc["name"].map(display_name)

    def setting(row):
        mode = row["reasoning_mode"]
        if mode == "effort":
            return row["effort"]
        if mode == "budget":
            return f"budget {int(row['budget']):,}"
        if mode in ("none", "disabled"):
            return "none" if mode == "none" else "disabled"
        raise ValueError(mode)

    fc["setting"] = fc.apply(setting, axis=1)
    return fc.set_index("dname")


def update_roster(fc):
    path = PAPER_DATA / "roster_table.tex"
    old = path.read_text()
    lines = read_lines(path)
    hcells = cells_of(next(l for l in lines if l.startswith("Model &")))
    col = hcells.index("FreeCiv")
    seen = 0
    for i, l in enumerate(lines):
        if not l.rstrip().endswith("\\\\") or l.startswith("Model &"):
            continue
        c = cells_of(l)
        nm = c[0].replace("\\_", "_")
        if nm in fc.index:
            c[col] = tex(fc.loc[nm, "setting"])
            lines[i] = join_cells(c)
            seen += 1
    assert seen == 24, seen
    write_lines(path, lines, old)


def main():
    rows = validation_rows()
    fc = freeciv_run_records()
    w = load_wide()
    update_validation(rows)
    update_roster(fc)
    cap = load_capability()
    both = cap.dropna()
    rng = np.random.default_rng(SEED)
    out = dict(generated=str(date.today()), script="forecastbench-sim-paper/src/fbsim_paper/assets/freeciv/update_shared_tables.py", seed=SEED, n_boot=N_BOOT,
               final=FINAL, sources={"wide": rel(WIDE), "score_items": rel(SCORE_ITEMS),
                                     "models_file": rel(MODELS_FILE), "run": RUN},
               sign_convention="rho between the capability score and (-1 x score); positive = more capable models score better",
               model_bootstrap=f"percentile bootstrap over the (capability, score) model pairs, {N_BOOT:,} resamples, "
                               f"numpy default_rng({SEED}) re-seeded per row and axis",
               cluster_bootstrap="resample the 8 anchor worlds with replacement, recompute every model's mean score from "
                                 "score_items over the items of the drawn worlds (with multiplicity), then Spearman rho",
               eci_vs_fb_spearman=spearman_stats(both.eci.values, both.fb.values, rng),
               rows=rows,
               run=dict(models=24, total_calls=int(w["total_calls"].sum()), total_cost_usd=float(w["total_cost_usd"].sum()),
                        per_model={n: dict(setting=r["setting"])
                                   for n, r in fc.iterrows()}))
    if not CHECK:
        (DATA / "freeciv_validation_stats.json").write_text(json.dumps(out, indent=1, default=float))
        print("wrote", rel(DATA / "freeciv_validation_stats.json"))
    for r in rows:
        e, c = r["eci"], r["eci_cluster"]
        print(f"  {r['score']:36s} rho {e['rho']:5.2f} {fmt_ci(e['ci_lo'], e['ci_hi'])} p {e['p']:.3f} games {fmt_ci(c['ci_lo'], c['ci_hi'])}")


if __name__ == "__main__":
    main()
