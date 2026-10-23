#!/usr/bin/env python3
"""The paper's baselines on the FreeCiv question sets, from the generator's candidates and the turn-60 reports.

    python make_freeciv_baselines.py --sets SETS_DIR --reports REPORTS_DIR --candidates CANDIDATES_DIR \
        --scores SCORE_ITEMS --out freeciv_baselines.json

Binary: the base rate, the mean q of the candidates with the same question template (family and the parameters in
its text, not the civilizations) at the same horizon in the other seven games, over every candidate with 0 < q < 1.
Natural conditionals: that base rate of Y, ignoring the revealed fact. Continuous: the turn-60 value from the report
(zero for counts of events after turn 60) plus the other games' change over the same horizon, over the eligible
continuous candidates. Also scores the alternatives the appendix compares, and the models' forecast levels per set.
Keys of the paper's scores are the columns of freeciv_results_wide.csv.
"""
import argparse, csv, gzip, json
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from fbsim_benchmark.scoring.freeciv import TAU, bits, pinball, truth_quantiles
from fbsim_paper.baselines import base_rates, change_quantiles

PARAMS = ("k", "metric", "gov", "tech", "wonder", "kind", "f")
LEVEL = {"NC1_value_at_T", "P5_techs_at_T", "P6_world_techs"}                      # the rest count events after turn 60
COLUMN = {"cities_count": "Cities", "population": "Population", "scores": "Score", "territory_size": "Territory"}
TAIL, TOP = 0.05, 0.95

ap = argparse.ArgumentParser()
ap.add_argument("--sets", type=Path, required=True, help="the draw's question sets (sets/draw_v1)")
ap.add_argument("--reports", type=Path, required=True, help="the turn-60 world reports (reports/)")
ap.add_argument("--candidates", type=Path, required=True, help="export_candidates.py's output")
ap.add_argument("--scores", type=Path, required=True, help="the run's score_items.csv.gz")
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
load = lambda name: json.load(open(a.sets / name))

# ---- binary: base rates over the candidates; the asked questions are among them
cand = list(csv.DictReader(open(a.candidates / "binary_candidates.csv")))
for c in cand:
    c["q"] = float(c["q"]); c["T"] = int(c["T"])
template = lambda c: (c["family"],) + tuple(c[p] for p in PARAMS)
by_id = {c["id"]: c for c in cand}
sets = {"bank_750.json": "mid", "tails_300.json": "tail", "mirrors_50.json": "mirror", "natcond_extra_turn1.json": "extra"}
asked = [dict(by_id[it["id"]], set=s) for name, s in sets.items() for it in load(name)]
KEYS = [lambda c: (c["T"], template(c)), template, lambda c: (c["T"], c["family"]), lambda c: c["family"]]
band = lambda c: "tail" if c["q"] <= TAIL else "top" if c["q"] >= TOP else "mid"


def in_sample(items, key):
    """The mean q of the item's own group, its own world included."""
    g = defaultdict(list)
    for c in items: g[key(c)].append(c["q"])
    return [float(np.mean(g[key(c)])) for c in items]


VARIANTS = {   # name: (pool, rates), all scored on the asked questions
    "simulator": (cand, lambda P: base_rates(P, [lambda c: 0])),
    "simulator_horizon": (cand, lambda P: base_rates(P, [lambda c: c["T"]])),
    "question": (cand, lambda P: base_rates(P, KEYS[1:])),
    "question_horizon": (cand, lambda P: base_rates(P, KEYS)),
    "question_horizon_in_sample": (cand, lambda P: in_sample(P, KEYS[0])),
    "question_horizon_within_set": (cand, lambda P: base_rates(P, [lambda c, k=k: (band(c), k(c)) for k in KEYS])),
    "question_horizon_asked_pool": (asked, lambda P: base_rates(P, KEYS)),
    "family_horizon": (cand, lambda P: base_rates(P, KEYS[2:])),
}
rates = {}
for name, (pool, fn) in VARIANTS.items():
    rates[name] = dict(zip([c["id"] for c in pool], fn(pool)))
scored = lambda s: [c for c in asked if c["set"] == s]


def binary_scores(r):
    return dict(mid=float(np.mean([(r[c["id"]] - c["q"]) ** 2 for c in scored("mid")])),
                tail=float(np.mean([bits(r[c["id"]], c["q"])[1] for c in scored("tail")])))


variants = {name: binary_scores(r) for name, r in rates.items()}
variants["constant"] = dict(mid=float(np.mean([(0.5 - c["q"]) ** 2 for c in scored("mid")])),
                            tail=float(np.mean([bits(0.05, c["q"])[1] for c in scored("tail")])))
rate = rates["question_horizon"]
pooled = [c for c in asked if c["set"] in ("mid", "tail", "mirror")]
# the paper's base rate per horizon on the mid-range, tail and mirror sets, for the by-horizon tables
HZ = sorted({c["T"] for c in asked})
brier = lambda cs: float(np.mean([(rate[c["id"]] - c["q"]) ** 2 for c in cs]))
# the mean base rate and mean q of the mid-range questions in each of the reliability figure's ten bands of q
edges = np.linspace(0.05, 0.95, 11)
mid_bands = []
for lo, hi in zip(edges[:-1], edges[1:]):
    cs = [c for c in scored("mid") if (lo < c["q"] <= hi) or (lo == edges[0] and c["q"] == lo)]
    mid_bands.append(dict(q=float(np.mean([c["q"] for c in cs])), rate=float(np.mean([rate[c["id"]] for c in cs])), n=len(cs)))
binary_by_horizon = {T: dict(mid=brier([c for c in scored("mid") if c["T"] == T]),
                             tail=float(np.mean([bits(rate[c["id"]], c["q"])[1] for c in scored("tail") if c["T"] == T])),
                             mirror=brier([c for c in scored("mirror") if c["T"] == T])) for T in HZ}

# questions behind each paper base rate: the other games' candidates at the first key level that has any
idx = [defaultdict(list) for _ in KEYS]
for c in cand:
    for j, k in enumerate(KEYS): idx[j][k(c)].append(c["world"])
size = []
for c in scored("mid") + scored("tail"):
    for j, k in enumerate(KEYS):
        n = sum(w != c["world"] for w in idx[j][k(c)])
        if n: size.append(n); break

# ---- natural conditionals: independence with the base rate of Y
cells = load("natcond_600.json")
natcond = [(rate[c["qid"]] - c["p_given"]) ** 2 for c in cells]
natcond_true_py = [(c["p"] - c["p_given"]) ** 2 for c in cells]
natcond_by = lambda k: {v: float(np.mean([x for c, x in zip(cells, natcond) if c[k] == v])) for v in sorted({c[k] for c in cells})}

# ---- continuous: climatological change over the eligible candidates
def turn60(world):
    """{civ id: {report column: value}} from the report's CURRENT STATE table."""
    lines = open(a.reports / world / "turn_060_report.txt").read().splitlines()
    i = lines.index("CURRENT STATE (TURN 60)") + 1
    head = [h.strip() for h in lines[i].split("|")]
    return {r[0]: dict(zip(head, r)) for r in ([c.strip() for c in x.split("|")] for x in lines[i + 2:]) if len(r) == len(head)}


C = np.load(a.candidates / "continuous_candidates.npz")
state, norm = {}, load("continuous_norm_constants.json")["constants"]
cont = {}
for i, w, fam, metric, T, subj, ys in zip(C["id"], C["world"], C["family"], C["metric"], C["T"], C["subj"], C["values"]):
    if fam not in LEVEL:
        last = 0.0
    else:
        s = state.setdefault(w, turn60(w))
        last = (sum(float(c["Techs"]) for c in s.values()) if fam == "P6_world_techs"
                else float(s[subj.split()[0]][COLUMN[metric] if fam == "NC1_value_at_T" else "Techs"]))
    key = fam + ("/" + metric if fam == "NC1_value_at_T" else "")
    cont[str(i)] = dict(world=str(w), key=key, T=int(T), ys=ys, last=last, change=ys - last, c=norm[key]["constant"])
pool = defaultdict(list)
for it in cont.values():
    pool[it["key"], it["T"]].append(it)
others = lambda it, k: [o[k] for o in pool[it["key"], it["T"]] if o["world"] != it["world"]]
CONT_VARIANTS = {   # the climatological change, and the appendix's alternatives
    "change": lambda it: change_quantiles(it["last"], others(it, "change"), TAU, lo=0),
    "last": lambda it: np.full(len(TAU), it["last"]),
    "climatology": lambda it: change_quantiles(0.0, others(it, "ys"), TAU, lo=0)}
excess_ncrps = lambda f, it: (pinball(f, it["ys"]) - pinball(truth_quantiles(it["ys"]), it["ys"])) / it["c"]
cont_asked = [cont[q["id"]] for q in load("continuous_300.json")]
cont_variants = {name: float(np.mean([excess_ncrps(v(it), it) for it in cont_asked])) for name, v in CONT_VARIANTS.items()}
ncrps, raw, exc = [], defaultdict(list), defaultdict(list)   # excess nCRPS, and nCRPS and excess by horizon
for it in cont_asked:
    f = CONT_VARIANTS["change"](it)
    ncrps.append(excess_ncrps(f, it))
    raw[it["T"]].append(pinball(f, it["ys"]) / it["c"]); exc[it["T"]].append(ncrps[-1])

# ---- the models' forecasts per set, against the truth and the base rate
fc = defaultdict(lambda: defaultdict(list))   # set -> model -> [(forecast, q, base rate)]
SET = {"bank": "mid", "tails": "tail", "mirrors": "mirror"}
with gzip.open(a.scores, "rt") as f:
    for r in csv.DictReader(f):
        if r["set"] in SET and r["arm"] == "t1" and r["parsed"] == "1" and r["p"] != "":
            fc[SET[r["set"]]][r["model"]].append((float(r["p"]), float(r["q"]), rate[r["item"]]))
levels = {}
for s, models in fc.items():
    rows = np.array([x for v in models.values() for x in v])
    levels[s] = dict(mean_forecast=float(rows[:, 0].mean()), mean_q=float(rows[:, 1].mean()), mean_base_rate=float(rows[:, 2].mean()),
                     corr_forecast_q=float(np.corrcoef(rows[:, 0], rows[:, 1])[0, 1]),
                     corr_base_rate_q=float(np.corrcoef(rows[:, 2], rows[:, 1])[0, 1]),
                     corr_forecast_q_models=[float(np.corrcoef(*np.array(v)[:, :2].T)[0, 1]) for v in models.values()])
mean_f = {s: {m: float(np.mean([x[0] for x in v])) for m, v in fc[s].items()} for s in fc}
models = sorted(mean_f["mid"])
levels["rank_corr_mean_forecast_mid_tail"] = float(spearmanr([mean_f["mid"][m] for m in models], [mean_f["tail"][m] for m in models]).correlation)
levels["mean_tail_forecast"] = mean_f["tail"]

out = dict(bank_all_excess_brier=variants["question_horizon"]["mid"], tails_all_excess_bits=variants["question_horizon"]["tail"],
           selected_excess_brier=float(np.mean([(rate[c["id"]] - c["q"]) ** 2 for c in pooled])),
           mirrors_all_excess_brier=brier(scored("mirror")), binary_by_horizon=binary_by_horizon, mid_range_bands=mid_bands,
           continuous_ncrps_by_horizon={T: float(np.mean(v)) for T, v in sorted(raw.items())},
           continuous_excess_by_horizon={T: float(np.mean(v)) for T, v in sorted(exc.items())},
           continuous_all_excess_ncrps_global=float(np.mean(ncrps)), natcond_all_excess_t2=float(np.mean(natcond)),
           natcond_by_horizon=natcond_by("T"), natcond_by_block=natcond_by("block"),
           natcond_true_py_excess_t2=float(np.mean(natcond_true_py)), binary_variants=variants, continuous_variants=cont_variants,
           forecast_levels=levels,
           n=dict(candidates=len(cand), asked=len(asked), mid=len(scored("mid")), tail=len(scored("tail")), selected=len(pooled),
                  continuous_candidates=len(cont), continuous=len(ncrps), natcond=len(natcond)),
           questions_per_base_rate=dict(median=float(np.median(size)), min=int(min(size)), max=int(max(size))),
           method=dict(binary="mean q of the candidates with the same template and horizon in the other games (0 < q < 1)",
                       natcond="the binary base rate of Y, ignoring X; natcond_true_py_excess_t2 uses the true p(Y) instead",
                       continuous="turn-60 value (0 for counts after turn 60) plus quantiles of the other games' change, same family and horizon"))
with open(a.out, "w") as f:
    json.dump(out, f, indent=1); f.write("\n")
print(f"mid {out['bank_all_excess_brier']:.4f}, tail {out['tails_all_excess_bits']:.4f}, selected {out['selected_excess_brier']:.4f}, "
      f"continuous {out['continuous_all_excess_ncrps_global']:.4f}, natcond {out['natcond_all_excess_t2']:.4f}")
print("wrote", a.out)
