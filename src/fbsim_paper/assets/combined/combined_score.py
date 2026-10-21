# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy==2.2.6", "scipy==1.15.3", "matplotlib==3.10.3"]
# ///
"""Combined score of section 7: additive log-loss model log l_mc = delta_c - theta_m, alternating least squares,
theta centred at zero, cells with a missing value left out of the sums, losses clipped at 1e-4.
Inputs use Micropolis excess nCRPS and tail excess bits from the model-score CSV,
FreeCiv excess nCRPS from the full-precision results CSV, and the repaired Starsim continuous excess losses (historical binary excluded),
so every cell is an excess score.
Reads only the paper checkout (the roster via paper_roster.py); plot_combined_score.py draws the figure from the
JSON this writes. Run with `combined_score.py --paper-root PAPER --out PAPER/data/combined_score.json`.
"""
import argparse, csv, json, re, sys
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from paper_roster import paper_roster
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--paper-root', type=Path, required=True)
ap.add_argument('--starsim-csv', type=Path, help='Defaults to the paper checkout CSV; use the rebuilt CSV when regenerating.')
ap.add_argument('--starsim', choices=['excess'], default='excess', help='Legacy locked8/proto16 modes are retired; archived skill CSVs are not paper inputs.')
ap.add_argument('--include-historical-binary', action='store_true', help='Appendix sensitivity only; excluded by default.')
ap.add_argument('--refit-boot', action='store_true', help='Diagnostic only; the published interval resamples fitted model scores without refitting.')
ap.add_argument('--out', type=Path, required=True, help='Output JSON; the macros and table go in the same directory')
a = ap.parse_args()
SQB = a.paper_root.resolve()
a.out.parent.mkdir(parents=True, exist_ok=True)
MODELS, ECI, SHORT = paper_roster(SQB)
MICRO_COLUMNS = {"Micropolis mid-range excess Brier": "mid_range_excess_brier",
                 "Micropolis tail excess bits": "tail_excess_bits",
                 "Micropolis excess nCRPS": "excess_ncrps"}
MICRO = {}
for row in csv.DictReader(open(SQB / "data/micropolis/micropolis_model_scores.csv")):
    name = SHORT.get(row["model"], row["model"])
    if name in MICRO:
        raise ValueError(f"Duplicate Micropolis model: {name}")
    values = {label: float(row[col]) for label, col in MICRO_COLUMNS.items()}
    if not all(np.isfinite(v) and v >= 0 for v in values.values()):
        raise ValueError(f"Invalid Micropolis losses: {name}")
    MICRO[name] = values
if set(MICRO) != set(MODELS):
    raise ValueError(f"Micropolis roster mismatch: {set(MICRO) ^ set(MODELS)}")
FREE_COLUMNS = {"FreeCiv bank excess Brier": "bank_all_excess_brier",
                "FreeCiv tail excess bits": "tails_all_excess_bits",
                "FreeCiv excess nCRPS": "continuous_all_excess_ncrps_global",
                "FreeCiv natural-conditional excess Brier": "natcond_all_excess_t2"}
FREE = {}
for row in csv.DictReader(open(SQB / "data/freeciv/freeciv_results_wide.csv")):
    name = SHORT.get(row["model"], row["model"])
    if name in FREE:
        raise ValueError(f"Duplicate FreeCiv model: {name}")
    FREE[name] = {label: float(row[col]) for label, col in FREE_COLUMNS.items()}
if set(FREE) != set(MODELS):
    raise ValueError(f"FreeCiv roster mismatch: {set(FREE) ^ set(MODELS)}")
def starsim(kind):
    S = {}
    rows = list(csv.DictReader(open(a.starsim_csv or SQB / "data/starsim/starsim_excess_long.csv")))
    for r in rows:
        if r["horizon"] != "pooled": continue
        n = SHORT.get(r["model"], r["model"]); S.setdefault(n, {})
        key = {("continuous", "interventional", "pooled(c25,c50,c90)"): "Starsim interventional excess CRPS", ("binary", "unconditional", "-"): "Starsim binary excess bits", ("continuous", "unconditional", "-"): "Starsim continuous excess CRPS"}.get((r["question_type"], r["condition"], r["rung"]))
        if key == 'Starsim binary excess bits' and not a.include_historical_binary: continue
        if key: S[n][key] = float(r["excess"]) if (r["excess"] and r["complete"] == "True") else None
    if set(S) != set(MODELS):
        raise ValueError("Starsim model names do not match the roster")
    if any(len(v) != (3 if a.include_historical_binary else 2) for v in S.values()):
        raise ValueError("Unexpected count of Starsim cells per model, including explicit missing values")
    return S
def fit(L, clip=1e-4, iters=500):
    """L: models x cells with nan for missing. returns theta (centred), delta, residual sd"""
    X = np.log(np.maximum(np.where(np.isnan(L), np.nan, L), clip)); M = ~np.isnan(X); theta = np.zeros(X.shape[0]); delta = np.zeros(X.shape[1])
    for _ in range(iters):
        delta = np.array([np.mean(X[M[:, c], c] + theta[M[:, c]]) for c in range(X.shape[1])])
        theta = np.array([np.mean(delta[M[m]] - X[m, M[m]]) for m in range(X.shape[0])]); theta -= theta.mean()
    R = (delta[None, :] - theta[:, None]) - X; return theta, delta, float(np.sqrt(np.nanmean(R ** 2)))
def rho(x, y): return float(spearmanr(x, y).correlation)
def boot(L, e, draws=10000, seed=2026, refit=False):
    rng = np.random.default_rng(seed); th = fit(L)[0]; out = []
    for _ in range(draws):
        i = rng.integers(0, len(e), len(e)); out.append(rho(e[i], fit(L[i])[0]) if refit else rho(e[i], th[i]))
    return float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))
def analyse(cells, label, refit):
    names = list(cells); L = np.array([[cells[c].get(m) if cells[c].get(m) is not None else np.nan for c in names] for m in MODELS], float); e = np.array([ECI[m] for m in MODELS])
    th, de, rsd = fit(L); r = rho(e, th); lo, hi = boot(L, e, refit=refit)
    single = {c: -rho(e[~np.isnan(L[:, i])], L[~np.isnan(L[:, i]), i]) for i, c in enumerate(names)}
    loo = {c: rho(e, fit(np.delete(L, i, 1))[0]) for i, c in enumerate(names)}
    agree = {c: rho(-L[~np.isnan(L[:, i]), i], th[~np.isnan(L[:, i])]) for i, c in enumerate(names)}
    print(f"[{label}] rho(theta, ECI) = {r:.3f} [{lo:.2f}, {hi:.2f}]  best single cell {max(single.values()):.3f} ({max(single, key=single.get)})  LOO {min(loo.values()):.3f}-{max(loo.values()):.3f}  resid sd {rsd:.3f}  agreement {min(agree.values()):.2f}-{max(agree.values()):.2f}")
    print("    single:", {c: round(v, 2) for c, v in single.items()}); print("    agreement:", {c: round(v, 2) for c, v in agree.items()})
    return dict(theta=dict(zip(MODELS, map(float, th))), rho=r, lo=lo, hi=hi, best_single=max(single.values()), single=single, loo=loo, resid_sd=rsd, agreement=agree)

# ---------------------------------------------------------------- outputs for the paper
def write_outputs(r, out_dir):
    out_dir = Path(out_dir)
    macros = {}
    for suffix, value in (("Rho", r["rho"]), ("Lo", r["lo"]), ("Hi", r["hi"]), ("Residual", r["resid_sd"]),
                          ("LooLo", min(r["loo"].values())), ("LooHi", max(r["loo"].values()))):
        macros["Combined" + suffix] = value
    for prefix, world in (("Core", False), ("Free", True)):
        values = [v for k, v in r["agreement"].items() if k.startswith("FreeCiv") == world]
        macros["Combined" + prefix + "AgreementLo"] = min(values)
        macros["Combined" + prefix + "AgreementHi"] = max(values)
    (out_dir / "combined_score_macros.tex").write_text(
        "% Generated by data/scripts/combined_score.py; do not edit by hand.\n" +
        "".join(f"\\newcommand{{\\{name}}}{{{value:.2f}}}\n" for name, value in macros.items()))
    order = sorted(MODELS, key=lambda m: -r["theta"][m])
    L = ["% Generated by data/scripts/combined_score.py; do not edit by hand. Micropolis: model-score CSV (excess nCRPS and tail bits); FreeCiv: results CSV (excess nCRPS). theta = fitted score summary from the additive log-loss model, centred at 0, higher = more skill. Starsim cells: excess CRPS / C_h; historical binary excluded unless explicitly requested (unconditional and interventional), September 16 run.",
         "\\begin{tabular}{@{}l r r@{}}", "\\toprule", "Model & ECI & $\\theta$ \\\\", "\\midrule"]
    for m in order:
        L.append(f"{m} & {ECI[m]:.1f} & ${r['theta'][m]:+.2f}$ \\\\")
    L += ["\\bottomrule", "\\end{tabular}"]; (out_dir / "combined_score_table.tex").write_text("\n".join(L) + "\n")

if __name__ == "__main__":
    S = starsim(a.starsim); cells = {}
    for k in MICRO_COLUMNS: cells[k] = {m: MICRO[m][k] for m in MICRO}
    for k in next(iter(S.values())): cells[k] = {m: S[m].get(k) for m in S}
    for k in ("FreeCiv excess nCRPS", "FreeCiv tail excess bits", "FreeCiv natural-conditional excess Brier", "FreeCiv bank excess Brier"): cells[k] = {m: FREE[m][k] for m in FREE}
    print("Starsim cells:", [k for k in cells if k.startswith("Starsim")], "| missing:", [(m, k) for m in S for k in S[m] if S[m][k] is None], "| binary zeros:", sum(1 for m in S if S[m].get("Starsim binary excess Brier") == 0))
    r = analyse(cells, "combined", a.refit_boot)
    if a.out: json.dump(dict(starsim=a.starsim, **r), open(a.out, "w"), indent=1)
    if a.out and a.starsim == "excess": write_outputs(r, Path(a.out).parent)
