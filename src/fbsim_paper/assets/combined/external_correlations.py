"""Combined score and ECI against external forecasting benchmarks (Appendix C, tab:external-benchmarks).
    python external_correlations.py --paper-root PAPER [--out OUT.json]

The scores are in external_scores.csv beside this script: Metaculus FutureEval (18 of our models) and Prophet Arena
Brier (9; Table 6 of arXiv 2510.17638v2), one row per model with the entry name as printed in the source. Models are
matched by name; for GPT-5 and Gemini 2.5 Flash the Prophet Arena row is the one closest to our reasoning setting
(minimal effort, reasoning on). Scores where lower is better are negated, so a positive rho means agreement.

For each benchmark: Spearman rho of theta (data/combined_score.json) and of ECI (data/freeciv/models_v2.csv) with the
benchmark over the models it covers. 95% CI: percentile bootstrap over models, 10,000 resamples of default_rng(2026)
with the models in sorted short-name order, the same resamples for theta and ECI; theta is not refitted. Also the
Spearman rho between each pair of FutureEval, Prophet Arena and ForecastBench overall (data/micropolis/model_scores.csv)
over the models both cover. The table's ForecastBench row repeats tab:combined-matched.
"""
import argparse, csv, json
from pathlib import Path
import numpy as np
from scipy import stats

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--paper-root', type=Path, required=True)
ap.add_argument('--out', type=Path, help='optional JSON of the results')
args = ap.parse_args()
DATA = args.paper_root.resolve() / 'data'
SHORT = {r['model']: r['short_name'] for r in csv.DictReader(open(DATA / 'model_names.csv'))}
THETA = json.load(open(DATA / 'combined_score.json'))['theta']
ECI = {SHORT[r['openrouter_id']]: float(r['eci']) for r in csv.DictReader(open(DATA / 'freeciv/models_v2.csv')) if r['openrouter_id'] in SHORT}
BENCH = {}
for r in csv.DictReader(open(Path(__file__).with_name('external_scores.csv'))):
    if r['model'] not in THETA: raise ValueError(f"{r['benchmark']}: {r['model']} is not in the roster")
    BENCH.setdefault(r['benchmark'], {})[r['model']] = float(r['score']) * (1 if r['higher_is_better'] == 'True' else -1)
BENCH['ForecastBench'] = {SHORT[r['slug']]: float(r['FBOverall']) for r in csv.DictReader(open(DATA / 'micropolis/model_scores.csv'))
                          if r['slug'] in SHORT and r['FBOverall']}


def rho(a, b, boot=True):
    keys = sorted(set(a) & set(b)); n = len(keys)
    x, y = np.array([a[k] for k in keys]), np.array([b[k] for k in keys])
    out = dict(n=n, rho=float(stats.spearmanr(x, y).statistic))
    if boot:
        rng = np.random.default_rng(2026)
        draws = [stats.spearmanr(x[i], y[i]).statistic for i in (rng.integers(0, n, n) for _ in range(10000))]
        out['ci'] = [float(v) for v in np.nanpercentile(draws, [2.5, 97.5])]
    return out


res = {b: dict(theta=rho(THETA, BENCH[b]), eci=rho(ECI, BENCH[b])) for b in ('FutureEval', 'Prophet Arena')}
pairs = {f'{a}|{b}': rho(BENCH[a], BENCH[b], boot=False)
         for a, b in (('FutureEval', 'Prophet Arena'), ('FutureEval', 'ForecastBench'), ('Prophet Arena', 'ForecastBench'))}
ci = lambda r: f"[{r['ci'][0]:.2f}, {r['ci'][1]:.2f}]"
for b, r in res.items():
    print(f"{b:14s} n={r['theta']['n']:2d}  theta {r['theta']['rho']:.2f} {ci(r['theta'])}  ECI {r['eci']['rho']:.2f} {ci(r['eci'])}")
for k, r in pairs.items():
    print(f"{k.replace('|', ' vs '):30s} n={r['n']:2d}  rho {r['rho']:.2f}")
if args.out:
    args.out.write_text(json.dumps(dict(script='forecastbench-sim-paper/src/fbsim_paper/assets/combined/external_correlations.py',
                                        benchmarks=res, benchmark_pairs=pairs), indent=1) + '\n')
