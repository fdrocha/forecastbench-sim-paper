#!/usr/bin/env python
"""FreeCiv's validation statistics: Spearman rho of each headline score with ECI and with ForecastBench overall.

    python src/fbsim_paper/assets/freeciv/validation_stats.py --paper-root PAPER [--check]

Writes data/freeciv/freeciv_validation_stats.json with every statistic and its method; combined/
make_validation_tables.py typesets the FreeCiv rows of the validation tables from it.  --check recomputes
without writing.

Sources (data/freeciv/): freeciv_results_wide.csv (headline scores, calls, cost),
score_items.csv.gz (per-item rows for the cluster bootstrap over the eight anchor games), model_scores.csv.
The FreeCiv statistics reproduce the retired data/compute_validation_stats.py (same seed, same resample
count, same bootstrap order).
"""
import json
import sys
from datetime import date

import numpy as np
from scipy.stats import spearmanr

from _common import (DATA, N_BOOT, RUN, SCORE_ITEMS, SEED, WIDE,
                     load_capability, load_items, load_wide, rel)

CHECK = "--check" in sys.argv[1:]

# The four FreeCiv headline rows: (table label, wide column, score_items set, score_items column).
FREECIV_SETS = [
    ("Excess nCRPS", "continuous_all_excess_ncrps_global", "continuous", "excess_ncrps_global"),
    ("Excess bits, tail", "tails_all_excess_bits", "tails", "excess_bits"),
    ("Excess Brier, natural conditional", "natcond_all_excess_t2", "natcond", "excess_t2"),
    ("Excess Brier, mid-range", "bank_all_excess_brier", "bank", "excess_brier"),
]


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


def main():
    rows = validation_rows()
    w = load_wide()
    cap = load_capability()
    both = cap.dropna()
    rng = np.random.default_rng(SEED)
    out = dict(generated=str(date.today()), script="forecastbench-sim-paper/src/fbsim_paper/assets/freeciv/validation_stats.py", seed=SEED, n_boot=N_BOOT,
               sources={"wide": rel(WIDE), "score_items": rel(SCORE_ITEMS),
                                     "run": RUN},
               sign_convention="rho between the capability score and (-1 x score); positive = more capable models score better",
               model_bootstrap=f"percentile bootstrap over the (capability, score) model pairs, {N_BOOT:,} resamples, "
                               f"numpy default_rng({SEED}) re-seeded per row and axis",
               cluster_bootstrap="resample the 8 anchor worlds with replacement, recompute every model's mean score from "
                                 "score_items over the items of the drawn worlds (with multiplicity), then Spearman rho",
               eci_vs_fb_spearman=spearman_stats(both.eci.values, both.fb.values, rng),
               rows=rows,
               run=dict(models=24, total_calls=int(w["total_calls"].sum()), total_cost_usd=float(w["total_cost_usd"].sum())))
    if not CHECK:
        (DATA / "freeciv_validation_stats.json").write_text(json.dumps(out, indent=1, default=float))
        print("wrote", rel(DATA / "freeciv_validation_stats.json"))
    for r in rows:
        e, c = r["eci"], r["eci_cluster"]
        print(f"  {r['score']:36s} rho {e['rho']:5.2f} {fmt_ci(e['ci_lo'], e['ci_hi'])} p {e['p']:.3f} games {fmt_ci(c['ci_lo'], c['ci_hi'])}")


if __name__ == "__main__":
    main()
