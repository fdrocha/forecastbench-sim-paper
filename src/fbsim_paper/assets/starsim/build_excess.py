"""Paper-facing Starsim outputs under the agreed EXCESS convention (2026-09-17), from cached runs only.

Reuses results/table/build_table.py loaders (same worlds, same jsonl, same median-over-reps) and
results/table/figures.py style, and writes to an output dir without touching the official files.

Scores (lower is better; continuous zero minimizes the five scored quantile losses; binary clipping leaves a positive endpoint floor)
  binary   midrange (min(P*,1-P*) > .05):  (p - P*)^2           [empty on Starsim: every certified item has P* in {0,1}
           tail     (min(P*,1-P*) <= .05): KL(P* || p) in bits, p clipped to [.001, .999]     or within .03 of it]
  continuous  excess = crps5(model quantiles p10..p90 vs all matched replay seeds) - crps5(truth quantiles, inverted_cdf)
              normalised by C_h = median over the 16 continuous items at horizon h (4 worlds x 4 conditions: unconditional,
              c25, c50, c90; 32 items over both horizons) of the truth's (p95 - p05), rounded to 1 significant figure.
              Computed from replay outcomes alone and shared across coverage levels.
Spearman rho vs ECI with a 95% percentile bootstrap over models (10,000 draws), complete models only.

  python build_excess.py --runs results/causal/rerun_lowest --out <dir>
"""
from __future__ import annotations
import argparse, csv, json, math, statistics, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from fbsim_benchmark.scoring.pandemic import crps5, kl_bits
from scipy.stats import spearmanr
from paths import analysis_modules, use_cached_runs
ANALYSIS_ROOT, bt, fg = analysis_modules()
import matplotlib.pyplot as plt  # noqa: E402
QK, TAU = bt.QKEYS, (0.10, 0.25, 0.50, 0.75, 0.90); CLIP, TAIL = 1e-3, 0.05

def one_sig(x): return float(f"{x:.1g}")

def constants():
    """C_h from the replay outcomes of all continuous items (unconditional + c25/c50/c90): 16 items per horizon."""
    ranges = defaultdict(list)
    for name in ("cont_uncond", "cont_int_c25", "cont_int_c50", "cont_int_c90"):
        _, _, _, _, wfile, tkey, _ = bt.SOURCES[name]
        for it in json.load(open(wfile))["items"]:
            ys = np.asarray(it[tkey]["samples"], float)
            ranges[it["horizon"]].append(float(np.quantile(ys, .95) - np.quantile(ys, .05)))
    C = {h: one_sig(float(np.median(v))) for h, v in ranges.items()}
    for h, c in C.items():
        if not c > 0: raise SystemExit(f"zero scale at horizon {h}")
    return C, {h: (len(v), float(np.median(v)), min(v), max(v)) for h, v in ranges.items()}

def score_all(C):
    long = []; per_item = {}
    roster = bt.load_roster()
    for name, (qtype, cond, rung, rfile, wfile, tkey, tmpl) in bt.SOURCES.items():
        items = {i["item_id"]: i for i in json.load(open(wfile))["items"]}; reps = bt.load_rows(rfile)
        pi = defaultdict(dict); rows_of = defaultdict(dict)
        for (m, iid), rs in reps.items():
            if iid not in items: continue
            it = items[iid]
            if qtype == "binary":
                p = statistics.median(r["p"] for r in rs); q = it[tkey]; tail = min(q, 1 - q) <= TAIL
                pi[m][iid] = dict(forecast=p, truth=q, stratum="tail" if tail else "midrange",
                                  excess=kl_bits(q, p) if tail else (p - q) ** 2, excess_brier=(p - q) ** 2, excess_bits=kl_bits(q, p))
            else:
                q = [statistics.median(r[k] for r in rs) for k in QK]; tr = it[tkey]; ys = np.asarray(tr["samples"], float)
                c = crps5(q, ys); floor = crps5([float(np.quantile(ys, t, method="inverted_cdf")) for t in TAU], ys)
                pi[m][iid] = dict(forecast_p50=q[2], truth_p50=tr["p50"], crps=c, floor=floor, C=C[it["horizon"]],
                                  excess_raw=c - floor, excess=(c - floor) / C[it["horizon"]])
            rows_of[m][iid] = rs
        per_item[name] = pi
        for m in roster:
            mid = m.openrouter_id
            for h in (40, 60, "pooled"):
                iids = [i for i in pi[mid] if h == "pooled" or items[i]["horizon"] == h]
                n_total = sum(1 for i in items if h == "pooled" or items[i]["horizon"] == h)
                row = dict(model=mid, name=m.name, eci=m.eci, fb_overall=m.fb_overall, question_type=qtype, condition=cond, rung=rung,
                           template=tmpl, horizon=h, n_items=len(iids), n_items_total=n_total, complete=len(iids) == n_total)
                rs = [r for i in iids for r in rows_of[mid][i]]
                row.update(bt.cell_meta(rs) if rs else dict(n_calls=0, cost_usd=0.0, reasoning_tokens_mean=float("nan"), completion_tokens_mean=float("nan")))
                if iids:
                    row["excess"] = float(np.mean([pi[mid][i]["excess"] for i in iids]))
                    if qtype == "binary":
                        row["n_tail"] = sum(pi[mid][i]["stratum"] == "tail" for i in iids); row["n_midrange"] = len(iids) - row["n_tail"]
                        row["excess_bits"] = float(np.mean([pi[mid][i]["excess_bits"] for i in iids])); row["excess_brier"] = float(np.mean([pi[mid][i]["excess_brier"] for i in iids]))
                    else:
                        for k in ("crps", "floor", "excess_raw"): row[k] = float(np.mean([pi[mid][i][k] for i in iids]))
                long.append(row)
    # pooled rungs: mean over the 24 item-rungs (equal weight per item-rung, family units), complete in all three
    by = defaultdict(list)
    for r in long:
        if r["question_type"] == "continuous" and r["condition"] == "interventional": by[(r["model"], r["horizon"])].append(r)
    for m in roster:
        for h in (40, 60, "pooled"):
            rs = by[(m.openrouter_id, h)]
            if not rs: continue
            row = dict(model=m.openrouter_id, name=m.name, eci=m.eci, fb_overall=m.fb_overall, question_type="continuous", condition="interventional",
                       rung="pooled(c25,c50,c90)", template="new_infections", horizon=h, n_items=sum(r["n_items"] for r in rs),
                       n_items_total=sum(r["n_items_total"] for r in rs), complete=all(r["complete"] for r in rs) and len(rs) == 3,
                       n_calls=sum(r["n_calls"] for r in rs), cost_usd=sum(r["cost_usd"] for r in rs),
                       reasoning_tokens_mean=float(np.mean([r["reasoning_tokens_mean"] for r in rs])), completion_tokens_mean=float(np.mean([r["completion_tokens_mean"] for r in rs])))
            if all("excess" in r for r in rs):
                for k in ("excess", "crps", "floor", "excess_raw"): row[k] = float(np.mean([r[k] for r in rs]))
            long.append(row)
    return long, per_item

def series(long, qtype, cond, rung, horizon="pooled"):
    return sorted([(r["model"], r["eci"], r["excess"], r["complete"]) for r in long if r["question_type"] == qtype and r["condition"] == cond
                   and r["rung"] == rung and r["horizon"] == horizon and "excess" in r], key=lambda t: t[1])

def skill_annotation(rho, lo, hi, n):
    """Display ECI versus negative loss; raw axes and raw rho_ci API stay unchanged.

    Negation reverses percentile endpoints: [lo, hi] -> [-hi, -lo].
    The caller supplies the original bootstrap; no uncertainty is recomputed here.
    """
    return (f"$\\rho(\\mathrm{{ECI}},-\\mathrm{{loss}})$ = {-rho:.2f} "
            f"[{-hi:.2f}, {-lo:.2f}], $n$ = {n}")


def fig_unconditional(long, out, C):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9)); fig.subplots_adjust(wspace=0.32)
    b = series(long, "binary", "unconditional", "-"); fg.scatter(a1, b, n_top=2, n_resid=4, n_low=0); rho, lo, hi, n = fg.rho_ci(b, seed=0)
    for label in a1.texts:
        if label.get_text() in {"Opus 5", "Fable"}:
            label.set_position((0, 15 if label.get_text() == "Opus 5" else 6))
            label.set_ha("center"); label.set_va("bottom")
    a1.axhline(0, ls="--", lw=0.6, color=fg.GREY)   # no "quantile oracle" label: with f clipped to .999 the truth itself scores -log2(.999) = 0.0014 bit, not 0
    a1.set_title("Binary, unconditional", fontsize=8); a1.set_xlabel("Epoch Capabilities Index"); a1.set_ylabel("Excess log score (bits; lower is better)")
    vals = [p[2] for p in b if p[3]]; n01 = sum(v <= 0.01 for v in vals)
    a1.text(0.98, 0.80, f"{n01} of {len(vals)} models within 0.01 bit of the truth", transform=a1.transAxes, ha="right", fontsize=6, color=fg.GREY)
    a1.text(0.98, 0.92, skill_annotation(rho, lo, hi, n), transform=a1.transAxes, ha="right", fontsize=7.5)
    c = series(long, "continuous", "unconditional", "-"); fg.scatter(a2, c, n_top=3, n_resid=3, n_low=0);
    # Place the crowded high-capability labels explicitly, leaving every point unchanged.
    offsets = {"GPT-5.6 Sol": (-33, 17), "Fable": (5, 53), "Opus 5": (-14, 35)}
    for label in list(a2.texts):
        if label.get_text() in offsets:
            label.remove()
    for model, eci, value, _ in c:
        name = fg.SHORT.get(model, model)
        if name in offsets:
            a2.annotate(name, (eci, value), xytext=offsets[name], textcoords="offset points",
                        ha="center", va="center", fontsize=6,
                        arrowprops=dict(arrowstyle="-", color=fg.GREY, lw=0.4))
    rho2, lo2, hi2, n2 = fg.rho_ci(c, seed=0)
    a2.axhline(0, ls="--", lw=0.6, color=fg.GREY); a2.text(0.02, 0.0, "quantile oracle", transform=a2.get_yaxis_transform(), ha="left", va="bottom", fontsize=6, color=fg.GREY)
    a2.set_title("Continuous, unconditional", fontsize=8); a2.set_xlabel("Epoch Capabilities Index"); a2.set_ylabel("Excess CRPS / $C$ (lower is better)")
    a2.text(0.98, 0.92, skill_annotation(rho2, lo2, hi2, n2), transform=a2.transAxes, ha="right", fontsize=7.5)
    fig.savefig(out / "fig_starsim_unconditional.pdf", bbox_inches="tight"); fig.savefig(out / "fig_starsim_unconditional.png", dpi=200, bbox_inches="tight"); plt.close(fig)
    cv = sorted(p[2] for p in c if p[3])
    return {"binary": dict(rho=rho, lo=lo, hi=hi, n=n, n_within_001_bit=n01, min=min(vals), max=max(vals), median=float(np.median(vals))),
            "continuous": dict(rho=rho2, lo=lo2, hi=hi2, n=n2, min=cv[0], max=cv[-1], median=float(np.median(cv)))}

def fig_interventional(long, out):
    pooled = series(long, "continuous", "interventional", "pooled(c25,c50,c90)")
    fig = plt.figure(figsize=(7.2, 3.1)); gs = fig.add_gridspec(3, 2, width_ratios=[2.6, 1.0], hspace=0.55, wspace=0.28)
    ax = fig.add_subplot(gs[:, 0]); fg.scatter(ax, pooled); rho, lo, hi, n = fg.rho_ci(pooled, seed=0)
    ax.axhline(0, ls="--", lw=0.6, color=fg.GREY); ax.text(0.99, 0.0, "quantile oracle", transform=ax.get_yaxis_transform(), ha="right", va="bottom", fontsize=6, color=fg.GREY)
    ax.set_xlabel("Epoch Capabilities Index"); ax.set_ylabel("Interventional excess CRPS / $C$ (lower is better)"); ax.set_title("All rungs pooled", fontsize=8, loc="left")
    inc = [p for p in pooled if not p[3]]
    note = skill_annotation(rho, lo, hi, n) + ("\nopen marker: incomplete, not in $\\rho$" if inc else "")
    ax.text(0.98, 0.97, note, transform=ax.transAxes, ha="right", va="top", fontsize=7)
    stats = {"pooled": dict(rho=rho, lo=lo, hi=hi, n=n)}
    for i, rung in enumerate(("c25", "c50", "c90")):
        axs = fig.add_subplot(gs[i, 1]); pts = series(long, "continuous", "interventional", rung); fg.scatter(axs, pts, labels=False)
        r2, l2, h2, n2 = fg.rho_ci(pts, seed=0); stats[rung] = dict(rho=r2, lo=l2, hi=h2, n=n2)
        axs.axhline(0, ls="--", lw=0.6, color=fg.GREY)
        axs.set_title(f"{rung[1:]}% coverage: $\\rho_s$ = {-r2:.2f} [{-h2:.2f}, {-l2:.2f}], $n$ = {n2}", fontsize=6, pad=2)
        if i == 2: axs.set_xlabel("Epoch Capabilities Index", fontsize=7)
        else: axs.set_xticklabels([])
    fig.savefig(out / "fig_starsim_interventional.pdf", bbox_inches="tight"); fig.savefig(out / "fig_starsim_interventional.png", dpi=200, bbox_inches="tight"); plt.close(fig)
    return stats

def fig_horizon(long, out):
    cells = defaultdict(dict)
    for r in long: cells[(r["question_type"], r["condition"], r["rung"], r["horizon"])][r["model"]] = r
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.4), sharey=True); fig.subplots_adjust(wspace=0.12); stats = {}
    YMAX = 3.0
    for ax, rung in zip(axes, ("c25", "c50", "c90")):
        d40 = cells[("continuous", "interventional", rung, 40)]; d60 = cells[("continuous", "interventional", rung, 60)]
        ms = [m for m in d40 if d40[m]["complete"] and d60.get(m, {}).get("complete")]
        s40 = np.array([d40[m]["excess"] for m in ms]); s60 = np.array([d60[m]["excess"] for m in ms])
        for a, b in zip(s40, s60): ax.plot([40, 60], [a, b], color=fg.GREY, lw=0.5, alpha=0.7, zorder=1)
        q40 = np.percentile(s40, [25, 75]); q60 = np.percentile(s60, [25, 75])
        ax.fill_between([40, 60], [q40[0], q60[0]], [q40[1], q60[1]], color="#d9d9d9", alpha=0.6, zorder=0, lw=0)
        ax.plot([40, 60], [s40.mean(), s60.mean()], color=fg.GREEN, lw=2.2, marker="o", ms=4, zorder=3)
        ax.text(39.2, s40.mean(), f"{s40.mean():.2f}", ha="right", va="center", fontsize=6.5); ax.text(60.8, s60.mean(), f"{s60.mean():.2f}", ha="left", va="center", fontsize=6.5)
        ax.axhline(0, ls="--", lw=0.6, color=fg.GREY); ax.set_xticks([40, 60]); ax.set_xlim(36, 64); ax.set_ylim(-0.05, YMAX); ax.set_xlabel("Forecast horizon (day)")
        ax.set_title(f"{rung[1:]}% coverage", fontsize=8)
        stats[rung] = dict(mean40=float(s40.mean()), mean60=float(s60.mean()), worse_at_60=int((s60 > s40).sum()), n=len(ms), clipped=int(((s40 > YMAX) | (s60 > YMAX)).sum()),
                           median40=float(np.median(s40)), median60=float(np.median(s60)))
    axes[0].set_ylabel("Interventional excess CRPS / $C$\n(lower is better)")
    axes[2].text(0.98, 0.0, "quantile oracle", transform=axes[2].get_yaxis_transform(), ha="right", va="bottom", fontsize=6, color=fg.GREY)
    from matplotlib.lines import Line2D; from matplotlib.patches import Patch
    axes[2].legend(handles=[Line2D([], [], color=fg.GREEN, lw=2.2, marker="o", ms=4, label="mean over models"), Patch(facecolor="#d9d9d9", label="interquartile range"),
                            Line2D([], [], color=fg.GREY, lw=0.6, label="one model")], loc="upper right", fontsize=6, frameon=False)
    fig.savefig(out / "fig_starsim_horizon_normalized.pdf", bbox_inches="tight"); fig.savefig(out / "fig_starsim_horizon_normalized.png", dpi=200, bbox_inches="tight"); plt.close(fig)
    return stats

def per_item_table(per_item, out, C):
    ORDER = [("binary_uncond", "Binary, unconditional"), ("cont_uncond", "Continuous, unconditional"), ("cont_int_c25", "Continuous, 25\\% coverage"),
             ("cont_int_c50", "Continuous, 50\\% coverage"), ("cont_int_c90", "Continuous, 90\\% coverage"), ("binary_int_c90", "Binary, 90\\% coverage"), ("binary_int_hold", "Binary, hold")]
    R0 = {0.03: 1.8, 0.04: 2.4, 0.05: 3.0, 0.065: 3.9}; roster = bt.load_roster(); rows = []; rec = []
    for name, label in ORDER:
        qtype, cond, rung, rfile, wfile, tkey, tmpl = bt.SOURCES[name]; W = json.load(open(wfile)); items = W["items"]; pi = per_item[name]
        complete = [m.openrouter_id for m in roster if all(it["item_id"] in pi.get(m.openrouter_id, {}) for it in items)]
        for it in items:
            ex = np.array([pi[m][it["item_id"]]["excess"] for m in complete])
            if qtype == "binary":
                truth = it[tkey]; Wd = {w["world_id"]: w for w in W["worlds"]}[it["world_id"]]
                world = f"{Wd['beta_r']:.3f} / {Wd['beta_s']:.3f}"; cov = Wd.get("coverage", 0.9 if rung == "c90" else None)
                tr_txt, floor, scale = f"{truth:.2f}", "--", "--"
            else:
                world = f"{it['beta']:.3f} ({R0[it['beta']]:.1f})"; cov = {"c25": 0.25, "c50": 0.5, "c90": 0.9}.get(rung)
                tr_txt = f"{it[tkey]['p50']:.0f}"; floor = f"{pi[complete[0]][it['item_id']]['floor']:.0f}"; scale = f"{C[it['horizon']]:.0f}"
            rows.append((label, it["item_id"], world, "--" if cov is None else f"{int(cov*100)}", it["horizon"], tr_txt, floor, scale,
                         f"{np.median(ex):.2f}", f"{ex.min():.2f}", f"{ex.max():.2f}", len(complete)))
            rec.append(dict(set=name, item=it["item_id"], world=world, coverage=cov, horizon=it["horizon"], truth=tr_txt, floor=floor, C=scale,
                            excess_median=float(np.median(ex)), excess_min=float(ex.min()), excess_max=float(ex.max()), n=len(complete)))
    lines = ["\\begin{tabular}{@{}l l l r r r r r r r r@{}}", "\\toprule",
             "Set & Item & $\\beta$ ($R_0$) or $\\beta_R$ / $\\beta_S$ & Cov.\\ \\% & Day & Truth & Floor & $C$ & Excess med.\\ & Min & Max \\\\", "\\midrule"]
    last = None
    for r in rows:
        if r[0] != last:
            if last is not None: lines.append("\\addlinespace")
            last = r[0]; first = True
        cells = [r[0] if first else ""] + [str(x) for x in r[1:11]]; first = False
        cells[1] = "\\texttt{" + cells[1].replace("_", "\\_") + "}"; lines.append(" & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (out / "per_item_table.tex").write_text("\n".join(lines) + "\n"); json.dump(rec, open(out / "per_item_table.json", "w"), indent=1)
    return rec

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--analysis-root", type=Path, default=Path.cwd()); ap.add_argument("--runs", required=True); ap.add_argument("--out", required=True); a = ap.parse_args()
    use_cached_runs(bt, Path(a.runs).resolve()); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    C, Cinfo = constants(); long, per_item = score_all(C)
    cols = ["model", "name", "eci", "fb_overall", "question_type", "condition", "rung", "template", "horizon", "n_items", "n_items_total", "complete",
            "n_calls", "cost_usd", "reasoning_tokens_mean", "completion_tokens_mean", "excess", "n_tail", "n_midrange", "excess_bits", "excess_brier", "crps", "floor", "excess_raw"]
    with open(out / "starsim_excess_long.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in long: w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})
    su = fig_unconditional(long, out, C); si = fig_interventional(long, out); sh = fig_horizon(long, out); rec = per_item_table(per_item, out, C)
    # binary supplementary columns + strata
    extra = {}
    for name in ("binary_int_c90", "binary_int_hold", "cont_int_c25", "cont_int_c50", "cont_int_c90"):
        qtype, cond, rung = bt.SOURCES[name][:3]; pts = series(long, qtype, cond, rung); r, lo, hi, n = fg.rho_ci(pts, seed=0)
        vals = [p[2] for p in pts if p[3]]; extra[name] = dict(rho=r, lo=lo, hi=hi, n=n, mean=float(np.mean(vals)), median=float(np.median(vals)), min=min(vals), max=max(vals))
    strata = defaultdict(int)
    for name, pi in per_item.items():
        for m, d in pi.items():
            for iid, v in d.items():
                if "stratum" in v: strata[f"{name}|{v['stratum']}"] += 1
    nums = dict(C=C, C_info={h: dict(n_items=v[0], median_range=v[1], min_range=v[2], max_range=v[3]) for h, v in Cinfo.items()},
                unconditional=su, interventional=si, horizon=sh, other_columns=extra, strata_model_item_cells=dict(strata),
                validation=dict(min_excess_cont=min(v["excess"] for n, pi in per_item.items() if n.startswith("cont") for d in pi.values() for v in d.values()),
                                min_excess_bin=min(v["excess"] for n, pi in per_item.items() if n.startswith("binary") for d in pi.values() for v in d.values())),
                provenance=dict(runs=str(Path(a.runs).resolve()), grid=list(TAU), clip=CLIP, tail=TAIL, bootstrap="10,000 draws over models, ECI seed 0; ForecastBench validation seed 2026"))
    json.dump(nums, open(out / "numbers.json", "w"), indent=1, default=float)
    # Skill-oriented LaTeX macros; numbers.json retains raw loss correlations.
    def mac(k, v): return f"\\newcommand{{\\{k}}}{{{v}}}"
    M = [mac("ssCfourty", f"{C[40]:.0f}"), mac("ssCsixty", f"{C[60]:.0f}")]
    for key, d in (("BinUncond", su["binary"]), ("ContUncond", su["continuous"]), ("IntPooled", si["pooled"]), ("IntCtf", si["c25"]), ("IntCfifty", si["c50"]), ("IntCninety", si["c90"]),
                   ("BinCninety", extra["binary_int_c90"]), ("BinHold", extra["binary_int_hold"])):
        M += [mac(f"ssRho{key}", f"{-d['rho']:.2f}"), mac(f"ssRhoLo{key}", f"{-d['hi']:.2f}"), mac(f"ssRhoHi{key}", f"{-d['lo']:.2f}"), mac(f"ssN{key}", str(d["n"]))]
    (out / "starsim_excess_macros.tex").write_text("\n".join(M) + "\n")
    print(json.dumps(nums, indent=1, default=float)); print("[saved] ->", out)

if __name__ == "__main__":
    main()
