"""The validation tables: Spearman rho of each world's scores with ECI (Section 7) and with ForecastBench overall
(Appendix C). Standard library only:
    python3 make_validation_tables.py --paper-root PAPER

Writes data/validation_table_main.tex and data/validation_table_forecastbench.tex; the latter adds the partial
correlation given ECI from validation_partial_forecastbench.json (partial_correlations.py). Micropolis cells are its
\\MPD* macros (micropolis-macros.tex), its conditionals' from micropolis/micropolis_{natcond,intcond}_summary.json
when present; Starsim's come from starsim/integration_numbers.json and FreeCiv's from
freeciv/freeciv_validation_stats.json. Every rho is sign-adjusted so that positive means more capable models
score better; CI is the 95% percentile bootstrap over models; p is from scipy.stats.spearmanr.
"""
import argparse, json
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--paper-root", type=Path, required=True)
DATA = ap.parse_args().paper_root.resolve() / "data"

MICROPOLIS = [("Excess Brier, mid-range", "Binary"), ("Excess bits, tail", "Tail"), ("Excess nCRPS", "Continuous")]
MICROPOLIS_CONDITIONALS = [("Excess Brier, natural conditional", "natcond"),
                           ("Excess Brier, interventional conditional", "intcond")]
# (key in integration_numbers.json, label in the tables)
STARSIM = [("Excess CRPS, interventional", "Excess nCRPS, interventional"),
           ("Excess CRPS, continuous", "Excess nCRPS, continuous")]
# The combined-score cell of each row, keying validation_partial_forecastbench.json.
PARTIAL_KEY = {"Binary": "Micropolis mid-range excess Brier", "Tail": "Micropolis tail excess bits",
               "Continuous": "Micropolis excess nCRPS",
               "natcond": "Micropolis natural-conditional excess Brier",
               "intcond": "Micropolis interventional-conditional excess Brier",
               "Excess CRPS, interventional": "Starsim interventional excess CRPS",
               "Excess CRPS, continuous": "Starsim continuous excess CRPS",
               "bank_all_excess_brier": "FreeCiv bank excess Brier", "tails_all_excess_bits": "FreeCiv tail excess bits",
               "continuous_all_excess_ncrps_global": "FreeCiv excess nCRPS",
               "natcond_all_excess_t2": "FreeCiv natural-conditional excess Brier"}

def fmt_p(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"

def stat_cells(n, rho, lo, hi, p, with_n):
    ci = "--" if lo is None else f"$[{lo:.2f}, {hi:.2f}]$"  # no interval when too few resamples give a defined rho
    return ([str(n)] if with_n else []) + [f"${rho:.2f}$", ci, fmt_p(p)]

def block(world, rows):
    """Rows as (score label, cells); the world's name spans them."""
    return [(f"\\multirow{{{len(rows)}}}{{*}}{{{world}}}" if i == 0 else "") + " & " + " & ".join([label, *cells]) + r" \\"
            for i, (label, cells) in enumerate(rows)]

def table(axis, with_n, ci_header, comment, partial=None):
    pre = "MPD" if axis == "eci" else "MPDFB"
    def extra(key):
        if not partial:
            return []
        r = partial["rows"].get(PARTIAL_KEY[key])
        return stat_cells(r["n"], r["rho"], r["ci_lo"], r["ci_hi"], r["p"], False) if r else ["--", "", ""]
    micropolis = [(label, ([f"\\{pre}NModels{m}"] if with_n else [])
                   + [f"$\\{pre}Rho{m}Short$", f"\\{pre}Rho{m}CIModels", f"\\{pre}P{m}"] + extra(m)) for label, m in MICROPOLIS]
    for label, study in MICROPOLIS_CONDITIONALS:
        path = DATA / "micropolis" / f"micropolis_{study}_summary.json"
        if not path.is_file():  # a manuscript from before the conditionals
            continue
        c = json.load(open(path))
        if axis == "eci":
            n, rho, ci, p = c["n_models"], c["rho"], c["rho_ci_models"], c["rho_p"]
        else:
            fb = c["forecastbench"]
            n, rho, ci, p = fb["n"], fb["rho"], fb["ci_models"], fb["p"]
        lo, hi = ci or (None, None)
        micropolis.append((label, stat_cells(n, rho, lo, hi, p, with_n) + extra(study)))
    validation = json.load(open(DATA / "starsim" / "integration_numbers.json"))["starsim"]["validation"]
    starsim = []
    for key, label in STARSIM:
        s = validation[key][axis]   # raw loss orientation: flip rho and its interval
        starsim.append((label,
                        stat_cells(s["n"], -s["rho"], -s["hi"], -s["lo"], s["p"], with_n) + extra(key)))
    freeciv = [(r["score"], stat_cells(r[axis]["n"], r[axis]["rho"], r[axis]["ci_lo"], r[axis]["ci_hi"], r[axis]["p"], with_n)
                + extra(r["column"]))
               for r in json.load(open(DATA / "freeciv" / "freeciv_validation_stats.json"))["rows"]]
    cols = ("llrrlr" if with_n else "llrlr") + ("rlr" if partial else "")
    header = ["Simulation", "Score", *(["$n$"] if with_n else []), r"$\rho$", ci_header, "$p$"]
    group = []
    if partial:
        header += [r"$\rho$", ci_header, "$p$"]
        group = [r" & & \multicolumn{3}{c}{Bivariate} & \multicolumn{3}{c}{Partial, given ECI} \\",
                 r"\cmidrule(lr){3-5}\cmidrule(lr){6-8}"]
    lines = ["% Generated by forecastbench-sim-paper/src/fbsim_paper/assets/combined/make_validation_tables.py; do not edit by hand.",
             f"% {comment} Micropolis cells are its \\MPD* macros (rho to two decimals); Starsim: repaired continuous only,",
             "% 2,000 audit model resamples; FreeCiv: 'Excess Brier, natural conditional' is the turn-2 score.",
             r"\setlength{\tabcolsep}{3pt}", f"\\begin{{tabular}}{{{cols}}}", r"\toprule", *group, " & ".join(header) + r" \\", r"\midrule",
             *block("Micropolis", micropolis), r"\midrule", *block("Starsim", starsim), r"\midrule", *block("FreeCiv", freeciv),
             r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"

for name, text in [
        ("validation_table_main.tex", table("eci", True, r"95\% CI",
                                            "Spearman rho with ECI, sign-adjusted; 95% CI over models; p from scipy.stats.spearmanr.")),
        ("validation_table_forecastbench.tex", table("fb", False, "CI (models)",
                                                     "Spearman rho with ForecastBench overall, over the models that have it and the score, sign-adjusted; "
                                                     "95% CI over models; p from scipy.stats.spearmanr. Partial: ECI partialled out, "
                                                     "10,000 model resamples, p from t on n-3 df.",
                                                     json.load(open(DATA / "validation_partial_forecastbench.json"))))]:
    path = DATA / name
    if not path.exists() or path.read_text() != text:
        path.write_text(text)
        print(f"wrote {path}")
