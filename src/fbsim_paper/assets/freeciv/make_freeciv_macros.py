#!/usr/bin/env python
"""Every FreeCiv mid-range, tail and mirror number the prose quotes, as LaTeX macros (\\FCMid..., \\FCTail..., \\FCMir...).

    python src/fbsim_paper/assets/freeciv/make_freeciv_macros.py --paper-root PAPER

Run after validation_stats.py, make_freeciv_tables.py, make_freeciv_figs.py and selection_weights.py: it reads their
files in data/freeciv/ and checks its own numbers against them.  Writes data/freeciv_macros.tex and
data/freeciv/freeciv_prose_numbers.json, and the appendix's comparison of the mid-range results under equal and
selection weights (data/appendix_tables/freeciv_selection_weights.tex).
"""
import json
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from _common import (DATA, PAPER_DATA, RUN, SCORE_ITEMS, SHORT, TABLES, load_capability, load_items, load_wide,
                     models_by_eci, rel, spearman_signed, write_tabular)

HZ = [90, 120, 150, 180, 210]
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
UNDER_FAMILIES = ["NB6_event", "NB1_threshold"]   # "event and threshold questions"
MID_WORST = ["S7_any_destroyed", "S4_gov_change_count", "W4_lose_k"]   # "any city destroyed, the number of government changes, and cities lost"
TAIL_WORST = ["EX_government_at", "W6_peace_at", "NW5_wonder"]        # "a government in place at the horizon, a peace in effect, a wonder completed"
MINUS, PLUS = r"\ensuremath{-}", r"\ensuremath{+}"   # valid in text and in math


def decompose(f, q):
    """excess = squared bias + var f + var q - 2 cov(f, q)."""
    mf, mq = f.mean(), q.mean()
    return dict(bias2=(mf - mq) ** 2, var_f=((f - mf) ** 2).mean(), var_q=((q - mq) ** 2).mean(),
                cov2=2 * ((f - mf) * (q - mq)).mean(), total=((f - q) ** 2).mean())


def wavg(x, w):
    return float(np.average(np.asarray(x, float), weights=np.asarray(w, float)))


def wcorr(x, y, w):
    """Weighted Pearson correlation."""
    x, y, w = (np.asarray(v, float) for v in (x, y, w))
    mx, my = wavg(x, w), wavg(y, w)
    return float(wavg((x - mx) * (y - my), w) / np.sqrt(wavg((x - mx) ** 2, w) * wavg((y - my) ** 2, w)))


def kl_bits(q, p):
    q = np.clip(np.asarray(q, float), 1e-9, 1 - 1e-9)
    return q * np.log2(q / p) + (1 - q) * np.log2((1 - q) / (1 - p))


def worst_families(s, col, n=3):
    """The n hardest families of set s in the difficulty table's order (pooled by item counts)."""
    fh = pd.read_csv(DATA / "family_horizon_scores.csv")
    fh = fh[fh.set == s]
    return list(fh.groupby("family").apply(lambda d: (d.n * d[col]).sum() / d.n.sum(), include_groups=False).sort_values(ascending=False).index[:n])


def f2(x):
    return f"{x:.2f}".replace("-", MINUS)


def f3(x):
    return f"{x:.3f}".replace("-", MINUS)


def signed2(x):
    return (PLUS if x >= 0 else MINUS) + f"{abs(x):.2f}"


def pct(x):
    return f"{100 * x:.0f}\\%"


def rho_ci(rho, ci):
    return f"{f2(rho)} [{f2(ci[0])}, {f2(ci[1])}]"


items = load_items()
models = models_by_eci(load_wide())          # descending ECI, the order the bootstraps resample in
eci = load_capability().eci.reindex(models)
VAL = {r["column"]: r for r in json.load(open(DATA / "freeciv_validation_stats.json"))["rows"]}
SUM = json.load(open(DATA / "freeciv_summary.json"))
MIR = json.load(open(DATA / "freeciv_numbers.json"))["freeciv"]["mirrors"]
N = dict(run=RUN, generated=str(date.today()), source=rel(SCORE_ITEMS))
M = {}


def eci_stats(col):
    r = VAL[col]
    return dict(rho=r["eci"]["rho"], ci=[r["eci"]["ci_lo"], r["eci"]["ci_hi"]], p=r["eci"]["p"], games_ci=[r["eci_cluster"]["ci_lo"], r["eci_cluster"]["ci_hi"]],
                fb=dict(rho=r["fb"]["rho"], ci=[r["fb"]["ci_lo"], r["fb"]["ci_hi"]], p=r["fb"]["p"], n=r["fb"]["n"]))


def rho_macros(prefix, e):
    return {f"{prefix}Rho": f2(e["rho"]), f"{prefix}RhoLo": f2(e["ci"][0]), f"{prefix}RhoHi": f2(e["ci"][1]), f"{prefix}RhoP": f"{e['p']:.3f}",
            f"{prefix}RhoGamesLo": f2(e["games_ci"][0]), f"{prefix}RhoGamesHi": f2(e["games_ci"][1]),
            f"{prefix}FBRho": f2(e["fb"]["rho"]), f"{prefix}FBLo": f2(e["fb"]["ci"][0]), f"{prefix}FBHi": f2(e["fb"]["ci"][1]), f"{prefix}FBP": f"{e['fb']['p']:.3f}"}


# ---------------------------------------------------------------- mid-range (bank)
b = items[items.set == "bank"].copy()
assert b.item.nunique() == 750 and b.model.nunique() == 24
b["e"] = b.p - b.q
g = b.groupby("model")
ex = g.excess_brier.mean().reindex(models)
bias = g.e.mean().reindex(models)
disc = g.apply(lambda d: d.p.corr(d.q), include_groups=False).reindex(models)
uq = b.drop_duplicates("item")
flat = float(((0.5 - uq.q) ** 2).mean())
horizon = {T: float(b[b["T"] == T].groupby("model").excess_brier.mean().mean()) for T in HZ}
assert max(abs(VAL["bank_all_excess_brier"]["per_model_score"][m] - ex[m]) for m in models) < 1e-9, "validation stats are not from this run"
assert np.allclose([horizon[T] for T in HZ], SUM["fig_freeciv_horizon"]["bank"]["mean_over_models"], atol=1e-12)

# reliability figure: pooled bands and per-model bias, as the figure draws them
rel_ = SUM["fig_freeciv_reliability"]
pq, pp = rel_["pooled"]["q"], rel_["pooled"]["p"]
above = [i for i in range(len(pq)) if pp[i] > pq[i]]
k = len(above)
if above == list(range(k)):
    where = f"they lie above the truth in the {WORDS[k]} lowest intervals and below it in the {WORDS[10 - k]} highest"
elif above == list(range(10 - k, 10)):
    where = f"they lie below the truth in the {WORDS[10 - k]} lowest intervals and above it in the {WORDS[k]} highest"
else:
    where = f"they lie above the truth in {WORDS[k]} of the ten intervals"
assert np.allclose([rel_["per_model_bias_bank"][m] for m in models], bias.values, atol=1e-12)
rho_disc, p_disc, (disc_lo, disc_hi), _ = spearman_signed(eci.values, disc.values, lower_is_better=False)

# forecast-binned rows and the decomposition (per model, then averaged over models)
low, high = b[b.p < 0.1], b[b.p >= 0.9]
dec = pd.DataFrame([decompose(d.p, d.q) for _, d in g]).mean()

# families: pooled over models
fam = b.groupby("family").apply(lambda d: pd.Series(dict(items=d.item.nunique(), bias=d.e.mean(), disc=d.p.corr(d.q) if d.q.nunique() > 1 else np.nan,
                                                        loss=float(d.excess_brier.sum()))), include_groups=False)
worst = worst_families("bank", "excess")
assert worst == MID_WORST, f"the prose names {MID_WORST} as the hardest mid-range families, now {worst}"
comp = fam.loc["EX_comparative"]
assert comp.disc == fam.disc.max(), "comparative questions are no longer the most discriminated family"
under = fam.loc[UNDER_FAMILIES, "bias"]
e = eci_stats("bank_all_excess_brier")
assert e["ci"][0] < 0 < e["ci"][1], "sections 2 and 7 count the mid-range interval as including zero"
rhos = [VAL[c]["eci"]["rho"] for c in VAL]
N["midrange"] = dict(
    mean_over_models=float(ex.mean()), per_model=ex.to_dict(), best=ex.idxmin(), worst=ex.idxmax(), eci=e, freeciv_eci_rho_range=[min(rhos), max(rhos)],
    flat_0p5=flat, models_below_flat=int((ex < flat).sum()), models_negative_bias=int((bias < 0).sum()), bias_range=[float(bias.min()), float(bias.max())],
    discrimination=dict(per_model=disc.to_dict(), rho_eci=rho_disc, ci=[disc_lo, disc_hi], p=p_disc),
    rho_bias_eci=float(spearmanr(eci, bias)[0]), rho_excess_absbias=float(spearmanr(ex, bias.abs())[0]), rho_excess_disc=float(spearmanr(ex, disc)[0]),
    horizon_mean=horizon, reliability=dict(p_low=pp[0], q_low=pq[0], p_high=pp[-1], q_high=pq[-1], where=where),
    forecast_bins=dict(low=dict(f=float(low.p.mean()), q=float(low.q.mean()), rows=len(low)), high=dict(f=float(high.p.mean()), q=float(high.q.mean()), rows=len(high))),
    decomposition=dec.to_dict(), families=fam.to_dict(orient="index"), worst_families=worst,
    worst_items=int(fam.loc[worst, "items"].sum()), worst_loss_share=float(fam.loc[worst, "loss"].sum() / fam.loss.sum()),
    under_families=under.to_dict(), mean_q=float(uq.q.mean()))
# claims the prose makes in words; a change needs a rewrite, not just new numbers
assert N["midrange"]["models_below_flat"] == 0 and N["midrange"]["models_negative_bias"] == 24, \
    "the prose says every model has negative mean forecast error and loses to a constant 0.5"
M.update({"FCMidMean": f3(ex.mean()), "FCMidBest": f3(ex.min()), "FCMidBestModel": SHORT[ex.idxmin()], "FCMidWorst": f3(ex.max()), "FCMidWorstModel": SHORT[ex.idxmax()]})
M.update(rho_macros("FCMid", e))
M.update({
    "FCRhoMin": f2(min(rhos)), "FCRhoMax": f2(max(rhos)),
    "FCMidFlat": f3(flat), "FCMidNegBias": str(N["midrange"]["models_negative_bias"]),
    "FCMidBiasMin": f2(bias.min()), "FCMidBiasMax": f2(bias.max()),
    "FCMidDiscMin": f2(disc.min()), "FCMidDiscMinModel": SHORT[disc.idxmin()], "FCMidDiscMax": f2(disc.max()), "FCMidDiscMaxModel": SHORT[disc.idxmax()],
    "FCMidDiscRho": f2(rho_disc), "FCMidDiscLo": f2(disc_lo), "FCMidDiscHi": f2(disc_hi),
    "FCMidBiasEciRho": f2(N["midrange"]["rho_bias_eci"]), "FCMidExcessAbsBiasRho": f2(N["midrange"]["rho_excess_absbias"]),
    "FCMidExcessDiscRho": f2(N["midrange"]["rho_excess_disc"]),
    "FCMidCompBias": signed2(comp.bias), "FCMidCompDisc": f2(comp.disc), "FCMidUnderLo": f2(-under.max()), "FCMidUnderHi": f2(-under.min()),
    "FCMidHorizonLo": f3(min(horizon.values())), "FCMidHorizonHi": f3(max(horizon.values())), "FCMidHorizonFirst": f3(horizon[90]), "FCMidHorizonLast": f3(horizon[210]),
    "FCMidRelPLow": f2(pp[0]), "FCMidRelQLow": f2(pq[0]), "FCMidRelPHigh": f2(pp[-1]), "FCMidRelQHigh": f2(pq[-1]), "FCMidRelWhere": where,
    "FCMidLowF": f3(N["midrange"]["forecast_bins"]["low"]["f"]), "FCMidLowQ": f3(N["midrange"]["forecast_bins"]["low"]["q"]), "FCMidLowRows": f"{len(low):,}",
    "FCMidHighF": f3(N["midrange"]["forecast_bins"]["high"]["f"]), "FCMidHighQ": f3(N["midrange"]["forecast_bins"]["high"]["q"]), "FCMidHighRows": f"{len(high):,}",
    "FCMidDecTotal": f3(dec.total), "FCMidDecBias": f3(dec.bias2), "FCMidDecVarF": f3(dec.var_f), "FCMidDecVarQ": f3(dec.var_q), "FCMidDecCov": f3(dec.cov2),
    "FCMidDecBiasShare": pct(dec.bias2 / dec.total),
    "FCMidWorstItems": str(N["midrange"]["worst_items"]), "FCMidWorstShare": pct(N["midrange"]["worst_loss_share"]),
    "FCMidMeanQ": f3(N["midrange"]["mean_q"]),
})

# ---------------------------------------------------------------- mid-range under selection weights (appendix)
W = pd.read_csv(DATA / "freeciv_selection_weights.csv").set_index("item").w
assert set(W.index) == set(uq.item) and abs(W.sum() - 750) < 1e-9
gw = b.assign(w=b.item.map(W)).groupby("model")
ex_w = gw.apply(lambda d: wavg(d.excess_brier, d.w), include_groups=False).reindex(models)
disc_w = gw.apply(lambda d: wcorr(d.p, d.q, d.w), include_groups=False).reindex(models)
rho_w, p_w, ci_w, _ = spearman_signed(eci.values, ex_w.values)
rho_disc_w, p_disc_w, ci_disc_w, _ = spearman_signed(eci.values, disc_w.values, lower_is_better=False)
bias_share_w = np.mean([(wavg(d.p, d.w) - wavg(d.q, d.w)) ** 2 for _, d in gw]) / ex_w.mean()   # as dec.bias2 / dec.total
N["selection_weights"] = d = dict(
    weights=rel(DATA / "freeciv_selection_weights.csv"), mean_over_models=float(ex_w.mean()), per_model=ex_w.to_dict(),
    eci=dict(rho=rho_w, ci=ci_w, p=p_w), rank_corr_equal=float(spearmanr(ex, ex_w)[0]), max_rank_move=int((ex.rank() - ex_w.rank()).abs().max()),
    flat_0p5=wavg((0.5 - uq.q) ** 2, uq.item.map(W)), mean_q=wavg(uq.q, uq.item.map(W)), bias_share=float(bias_share_w),
    discrimination=dict(rho_eci=rho_disc_w, ci=ci_disc_w, p=p_disc_w), effective_items=float(W.sum() ** 2 / (W ** 2).sum()))
d["models_below_flat"] = int((ex_w < d["flat_0p5"]).sum())
# what the appendix says in words: the headline numbers barely move, the q-mix-sensitive ones move more
assert abs(d["mean_over_models"] - ex.mean()) < 0.01 and abs(rho_w - e["rho"]) < 0.05 and d["rank_corr_equal"] > 0.95, \
    "the appendix says weighting leaves the mean score, the ECI correlation and the ranking nearly unchanged"
assert d["bias_share"] < dec.bias2 / dec.total, "the appendix says squared bias is a smaller share of the excess under the weights"
assert d["flat_0p5"] > flat and d["models_below_flat"] == 0, "the appendix says constant 0.5 scores worse under the weights but still beats every model"
assert rho_disc_w < rho_disc, "the appendix says the discrimination correlation with ECI is weaker under the weights"
write_tabular(TABLES / "freeciv_selection_weights.tex", "@{}lrr@{}", [" & Equal weights & Selection weights"], [
    ["Mean excess Brier over models", f3(ex.mean()), f3(d["mean_over_models"])],
    [r"$\rho$ with ECI [95\% CI]", rho_ci(e["rho"], e["ci"]), rho_ci(rho_w, ci_w)],
    ["Rank correlation with equal weights", "---", f2(d["rank_corr_equal"])],
    ["Constant 0.5, excess Brier", f3(flat), f3(d["flat_0p5"])],
    ["Squared bias, share of excess Brier", pct(dec.bias2 / dec.total), pct(d["bias_share"])],
    [r"Discrimination: $\rho$ with ECI [95\% CI]", rho_ci(rho_disc, [disc_lo, disc_hi]), rho_ci(rho_disc_w, ci_disc_w)],
    [r"Mean $q$", f3(uq.q.mean()), f3(d["mean_q"])],
], tabcolsep="4pt", comment="The 750 mid-range questions with equal weights and with the selection weights of freeciv_selection_weights.csv.",
    script="make_freeciv_macros.py")

# ---------------------------------------------------------------- tails
t = items[items.set == "tails"].copy()
assert t.item.nunique() == 300 and t.model.nunique() == 24
g = t.groupby("model")
bits = g.excess_bits.mean().reindex(models)
meanf = g.p.mean().reindex(models)
uq = t.drop_duplicates("item")
flat05 = float(np.mean(kl_bits(uq.q, 0.05)))
horizon = {T: float(t[t["T"] == T].groupby("model").excess_bits.mean().mean()) for T in HZ}
assert max(abs(VAL["tails_all_excess_bits"]["per_model_score"][m] - bits[m]) for m in models) < 1e-9, "validation stats are not from this run"
assert np.allclose([horizon[T] for T in HZ], SUM["fig_freeciv_horizon"]["tails"]["mean_over_models"], atol=1e-12)
assert abs(SUM["reference_forecasters"]["tails_flat_0p05_bits"] - flat05) < 1e-12
worst = worst_families("tails", "bits")
assert worst == TAIL_WORST, f"the prose names {TAIL_WORST} as the hardest tail families, now {worst}"
e = eci_stats("tails_all_excess_bits")
N["tails"] = dict(
    mean_over_models=float(bits.mean()), per_model=bits.to_dict(), best=bits.idxmin(), worst=bits.idxmax(), eci=e,
    mean_forecast=dict(min=float(meanf.min()), max=float(meanf.max()), per_model=meanf.to_dict()), mean_q=float(uq.q.mean()),
    flat_0p05_bits=flat05, models_below_flat=int((bits < flat05).sum()), rho_bits_meanforecast=float(spearmanr(bits, meanf)[0]), horizon_mean=horizon,
    worst_families=worst, worst_items=int(uq.family.isin(worst).sum()),
    worst_loss_share=float(t.excess_bits[t.family.isin(worst)].sum() / t.excess_bits.sum()))
# claims the prose makes in words; a change needs a rewrite, not just new numbers
assert N["tails"]["models_below_flat"] == 0, "the prose says no model scores below a constant 0.05"
assert e["ci"][0] < 0 < e["ci"][1], "sections 2 and 7 count the tail interval as including zero"
M.update({"FCTailMean": f2(bits.mean()), "FCTailBest": f3(bits.min()), "FCTailBestModel": SHORT[bits.idxmin()],
          "FCTailWorst": f3(bits.max()), "FCTailWorstModel": SHORT[bits.idxmax()]})
M.update(rho_macros("FCTail", e))
M.update({
    "FCTailMeanFMin": f2(meanf.min()), "FCTailMeanFMax": f2(meanf.max()), "FCTailMeanQ": f2(N["tails"]["mean_q"]), "FCTailMeanQThree": f3(N["tails"]["mean_q"]),
    "FCTailFlat": f2(flat05), "FCTailBelowFlat": str(N["tails"]["models_below_flat"]), "FCTailRhoMeanF": f2(N["tails"]["rho_bits_meanforecast"]),
    "FCTailHorizonFirst": f2(horizon[90]), "FCTailHorizonLast": f2(horizon[210]),
    "FCTailWorstItems": str(N["tails"]["worst_items"]), "FCTailWorstShare": pct(N["tails"]["worst_loss_share"]),
})

# ---------------------------------------------------------------- mirrors (the table's numbers, from make_freeciv_tables.py)
mi = items[items.set == "mirrors"]
uq = mi.drop_duplicates("item")
assert len(uq) == 50
mex = {m: r["excess_brier"] for m, r in MIR["per_model"].items()}
assert max(abs(mex[m] - mi[mi.model == m].excess_brier.mean()) for m in models) < 6e-5, "mirror numbers are not from this run"
assert MIR["n_below_flat_0p5"] == 0, "the prose says no model scores below a constant 0.5 on the mirrors"
best, worst = min(mex, key=mex.get), max(mex, key=mex.get)
N["mirrors"] = dict(per_model=mex, best=best, worst=worst, flat_0p5=MIR["flat_0p5_excess"], mean_q=float(uq.q.mean()),
                    eci=dict(rho=MIR["spearman_vs_eci_signed"], ci=MIR["ci95_models_boot"], p=MIR["p"]))
M.update({
    "FCMirBest": f3(mex[best]), "FCMirBestModel": SHORT[best], "FCMirWorst": f3(mex[worst]), "FCMirWorstModel": SHORT[worst],
    "FCMirFlat": f3(MIR["flat_0p5_excess"]), "FCMirMeanQ": f3(N["mirrors"]["mean_q"]),
    "FCMirRho": f2(MIR["spearman_vs_eci_signed"]), "FCMirRhoLo": f2(MIR["ci95_models_boot"][0]), "FCMirRhoHi": f2(MIR["ci95_models_boot"][1]),
    "FCMirRhoP": f"{MIR['p']:.2f}",
})

(DATA / "freeciv_prose_numbers.json").write_text(json.dumps(N, indent=1, default=float))
lines = [f"% Generated by forecastbench-sim-paper/src/fbsim_paper/assets/freeciv/make_freeciv_macros.py from results/{RUN}; do not edit by hand.",
         "% FreeCiv mid-range, tail and mirror numbers quoted in the text."]
lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in M.items()]
(PAPER_DATA / "freeciv_macros.tex").write_text("\n".join(lines) + "\n")
print(f"wrote {rel(PAPER_DATA / 'freeciv_macros.tex')} ({len(M)} macros) and {rel(DATA / 'freeciv_prose_numbers.json')}")
for k_, v in M.items():
    print(f"  {k_:24s} {v}")
