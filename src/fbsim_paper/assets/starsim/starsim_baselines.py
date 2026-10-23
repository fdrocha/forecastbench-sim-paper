"""The paper's baselines on the Starsim continuous items, from the fixed-state truths and the cached forecasts.

The baseline forecasts new infections by the other three worlds' no-vaccine outcomes at the same horizon; under
vaccination it ignores the vaccine (independence). A second reference, the SIR forecast, integrates the SIR equations
the world report describes from the day-20 state it reports. Two diagnostics replace the baseline under vaccination by
the true no-vaccine distribution, and by each model's own no-vaccine forecast.
Reads the audit's rescore outputs, so it can run before integrate_fixed_state.py, which draws its numbers.
"""
import argparse, csv, json, re, statistics
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from fbsim_benchmark.scoring.pandemic import TAU, crps5
from fbsim_paper.baselines import change_quantiles
from paths import analysis_modules, use_cached_runs
ap = argparse.ArgumentParser(); ap.add_argument('--audit-root', type=Path, required=True); ap.add_argument('--analysis-root', type=Path, required=True)
ap.add_argument('--out', type=Path, required=True); args = ap.parse_args()
R = args.audit_root.resolve()/'rescore'
C = {40: 200., 60: 300.}  # the historical reference scales of integrate_fixed_state.py
RUNGS = ('c25', 'c50', 'c90')
unc = {it['item_id']: it for it in json.load(open(R/'cont_uncond_worlds.json'))['items']}
ints = {r: {it['item_id']: it for it in json.load(open(R/f'cont_int_{r}_worlds.json'))['items']} for r in RUNGS}
samples = lambda it, key: np.asarray(it[key]['samples'], float)
def excess(q, ys, h):
    return (crps5(q, ys) - crps5([float(np.quantile(ys, t, method='inverted_cdf')) for t in TAU], ys)) / C[h]
base = {i: change_quantiles(0., [samples(o, 'truth_base') for o in unc.values() if o['world_id'] != it['world_id'] and o['horizon'] == it['horizon']],
                            TAU, lo=0, hi=it['upper']) for i, it in unc.items()}
truth = {i: [float(np.quantile(samples(it, 'truth_base'), t, method='inverted_cdf')) for t in TAU] for i, it in unc.items()}

def sir(it):
    """New infections from day 20 to the horizon under the deterministic SIR model, from the report's numbers."""
    num = lambda pattern: float(re.search(pattern, it['report']).group(1).replace(',', ''))
    n, contacts, days = num(r'([\d,]+) people'), num(r'about ([\d.]+) contacts per day'), num(r'infectious for ([\d.]+) days')
    infectious, c20 = num(r'day 20: ([\d,]+) currently infectious'), num(r'd20:([\d,]+)')
    assert c20 == it['c20'], (it['item_id'], c20, it['c20'])
    beta = contacts * num(r'Transmission probability per contact per day ([\d.]+)')
    s0 = n - c20
    rhs = lambda t, y: [-beta * y[0] * y[1] / n, beta * y[0] * y[1] / n - y[1] / days]
    s = solve_ivp(rhs, (0, it['horizon'] - 20), [s0, infectious], rtol=1e-9).y[0, -1]
    return np.clip(np.full(len(TAU), s0 - s), 0, it['upper'])
sirf = {i: sir(it) for i, it in unc.items()}
score_unc = lambda f, h=None: float(np.mean([excess(f[i], samples(it, 'truth_base'), it['horizon']) for i, it in unc.items()
                                             if h is None or it['horizon'] == h]))
score_int = lambda f, h=None: {r: float(np.mean([excess(f[i], samples(ints[r][i], 'truth_int'), unc[i]['horizon']) for i in unc
                                                  if h is None or unc[i]['horizon'] == h])) for r in RUNGS}
by_rung = score_int(base); true_by_rung = score_int(truth); by_rung_horizon = {h: score_int(base, h) for h in C}

# Each model's no-vaccine forecast as its forecast under vaccination, on the models of the paper's interventional panel.
_, bt, _ = analysis_modules(args.analysis_root); use_cached_runs(bt, args.analysis_root/'results/causal/rerun_lowest')
def forecasts(name):
    return {k: [statistics.median(r[q] for r in rs) for q in bt.QKEYS] for k, rs in bt.load_rows(bt.SOURCES[name][3]).items()}
own_unc = forecasts('cont_uncond')
panel = {r['model']: float(r['excess']) for r in csv.DictReader(open(R/'paper_fixed_state_long.csv'))
         if r['rung'] == 'pooled(c25,c50,c90)' and r['horizon'] == 'pooled' and r['complete'] == 'True'}
own = {m: float(np.mean([excess(own_unc[m, i], samples(ints[r][i], 'truth_int'), unc[i]['horizon']) for r in RUNGS for i in unc])) for m in panel}

# The appendix's alternatives: new infections are counted from day 20, so the last value is zero, and the other worlds'
# values, being their changes, give the climatological change itself.
zero = {i: np.zeros(len(TAU)) for i in unc}
out = dict(unconditional=score_unc(base), unconditional_sir=score_unc(sirf),
           continuous_variants=dict(change=score_unc(base), last=score_unc(zero), sir=score_unc(sirf)),
           unconditional_by_horizon={h: score_unc(base, h) for h in C}, unconditional_sir_by_horizon={h: score_unc(sirf, h) for h in C},
           sir_forecast={i: float(f[0]) for i, f in sirf.items()}, truth_median={i: float(t[2]) for i, t in truth.items()},
           interventional=float(np.mean(list(by_rung.values()))), interventional_by_rung=by_rung,
           interventional_by_rung_horizon=by_rung_horizon, interventional_by_horizon={h: float(np.mean(list(v.values()))) for h, v in by_rung_horizon.items()},
           interventional_true_no_vaccine=float(np.mean(list(true_by_rung.values()))), interventional_true_no_vaccine_by_rung=true_by_rung,
           own_no_vaccine={m: dict(reused=own[m], actual=panel[m]) for m in panel},
           n_models_beat_own_no_vaccine=sum(panel[m] < own[m] for m in panel), n_models=len(panel),
           method=dict(baseline='quantiles of the other worlds\' no-vaccine new infections at the same horizon; the same forecast under vaccination',
                       sir='every quantile at the drop in susceptibles from day 20 to the horizon under dS/dt = -b S I/N, dI/dt = b S I/N - I/10, '
                           'b = contacts per day x the transmission probability, from S = population - infected by day 20 and I = currently infectious, all as reported',
                       interventional_true_no_vaccine='the true no-vaccine quantiles as the forecast under vaccination',
                       own_no_vaccine='each model\'s no-vaccine forecast scored under vaccination, against its own score there'))
args.out.write_text(json.dumps(out, indent=1)+'\n')
print(f"unconditional {out['unconditional']:.3f}, SIR {out['unconditional_sir']:.3f}, interventional {out['interventional']:.3f}, "
      f"true no-vaccine {out['interventional_true_no_vaccine']:.3f}; wrote {args.out}")
