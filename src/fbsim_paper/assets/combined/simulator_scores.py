"""Simulator-level combined scores (Appendix C): the additive log-loss fit of combined_score.py run on each simulator's
cells alone, and the Spearman correlations of the three scores with each other and with ECI.
    python simulator_scores.py --paper-root PAPER

Writes data/simulator_scores.json, data/simulator_scores_macros.tex (the ranges quoted in the text) and
data/simulator_correlation_table.tex: one row per pair, Spearman rho and the partial Spearman given ECI (rank
residuals on rank(ECI)), each with its CI. CIs: 95% percentile bootstrap over models, the first 3,000 rows of
default_rng(0).integers(0, 24, (5000, 24)) with models in sorted short-name order; theta is not refitted.
"""
import argparse, csv, json
from pathlib import Path
import numpy as np
from scipy import stats
from partial_correlations import partial_spearman as partial
from shading import shade

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--paper-root', type=Path, required=True)
DATA = ap.parse_args().paper_root.resolve() / 'data'
NAMES = {r['model']: r['short_name'] for r in csv.DictReader(open(DATA / 'model_names.csv'))}
COMBINED = json.load(open(DATA / 'combined_score.json'))['theta']
MODELS = sorted(COMBINED)   # this order fixes the bootstrap resamples
MICRO, FREE, STAR = 'micropolis/micropolis_model_scores.csv', 'freeciv/freeciv_results_wide.csv', 'starsim/starsim_excess_long.csv'
star = lambda qtype, cond, rung: (lambda r: r['horizon'] == 'pooled' and r['question_type'] == qtype
                                  and r['condition'] == cond and r['rung'] == rung)
SIMS = {'Micropolis': [(MICRO, c, None) for c in ('mid_range_excess_brier', 'tail_excess_bits', 'excess_ncrps')],
        'FreeCiv': [(FREE, c, None) for c in ('bank_all_excess_brier', 'tails_all_excess_bits',
                                              'continuous_all_excess_ncrps_global', 'natcond_all_excess_t2')],
        'Starsim': [(STAR, 'excess', star('continuous', 'unconditional', '-')),
                    (STAR, 'excess', star('continuous', 'interventional', 'pooled(c25,c50,c90)'))]}
# Micropolis conditionals, answered by a subset of the models, as in the combined score: only where the manuscript has them.
PARTIAL = [f'micropolis/micropolis_{s}_scores.csv' for s in ('natcond', 'intcond')]
from fbsim_paper.experiments import include_micropolis_conditionals
SIMS['Micropolis'] += [(p, 'excess_t2', None) for p in PARTIAL if include_micropolis_conditionals() and (DATA / p).is_file()]


def load(path, col, keep):
    """One loss per model; NaN if empty, the row is marked incomplete or the model was not asked."""
    out = {}
    for r in csv.DictReader(open(DATA / path)):
        if keep and not keep(r): continue
        m = NAMES.get(r['model'], r['model'])
        if m in out: raise ValueError(f'{path} {col}: two rows for {m}')
        out[m] = float(r[col]) if r[col] and r.get('complete', 'True') == 'True' else np.nan
    if set(out) != set(MODELS) and not (path in PARTIAL and set(out) <= set(MODELS)):
        raise ValueError(f'{path} {col}: roster mismatch')
    return [out.get(m, np.nan) for m in MODELS]


def fit(L, iters=500):
    """theta of log l_mc = delta_c - theta_m, alternating means, centered; higher is better."""
    Y = np.log(np.maximum(L, 1e-4)); theta = np.zeros(len(L))
    for _ in range(iters):
        delta = np.nanmean(Y + theta[:, None], axis=0)
        theta = np.nanmean(delta[None, :] - Y, axis=1); theta -= theta.mean()
    return theta


spearman = lambda a, b: float(stats.spearmanr(a, b).statistic)
cells = {s: np.column_stack([load(*c) for c in cs]) for s, cs in SIMS.items()}
assert np.abs(fit(np.hstack(list(cells.values()))) - [COMBINED[m] for m in MODELS]).max() < 1e-15, 'all-cell fit differs from combined_score.json'
eci_by = {NAMES.get(r['model'], r['model']): float(r['eci']) for r in csv.DictReader(open(DATA / FREE))}
series = {'ECI': np.array([eci_by[m] for m in MODELS]), **{s: fit(L) for s, L in cells.items()}}
idx = np.random.default_rng(0).integers(0, len(MODELS), size=(5000, len(MODELS)))[:3000]
pairs = {}
for i, a in enumerate(series):
    for b in list(series)[i + 1:]:
        x, y, e = series[a], series[b], series['ECI']
        out = {'spearman': (spearman(x, y), [spearman(x[j], y[j]) for j in idx])}
        if 'ECI' not in (a, b):
            out['partial_given_eci'] = (partial(x, y, e), [partial(x[j], y[j], e[j]) for j in idx])
        pairs[f'{a}|{b}'] = {k: dict(rho=r, ci=list(map(float, np.nanpercentile(d, [2.5, 97.5])))) for k, (r, d) in out.items()}

json_text = json.dumps(dict(script='forecastbench-sim-paper/src/fbsim_paper/assets/combined/simulator_scores.py',
                            n=len(MODELS), resamples=len(idx), theta={s: dict(zip(MODELS, map(float, series[s])))
                                                                       for s in SIMS}, pairs=pairs), indent=1) + '\n'
fmt = lambda v: f'{v:.2f}'.replace('-', '\\ensuremath{-}')
rho_cell = lambda r: shade(f"\\textbf{{{fmt(r)}}}", (1 - r) / 2)   # shaded as tab:rank-correlation
ci_cell = lambda c: f"[{fmt(c[0])}, {fmt(c[1])}]"
lines = ['% Generated by forecastbench-sim-paper/src/fbsim_paper/assets/combined/simulator_scores.py; do not edit by hand.',
         "% Spearman rho and partial Spearman given ECI per pair of ECI and the simulator-level combined scores (the combined-score",
         "% fit on one simulator's cells), 24 models; 95% CI over 3,000 model resamples. rho shaded green (+1), white (0), purple (-1).",
         '\\setlength{\\tabcolsep}{6pt}', '\\renewcommand{\\arraystretch}{1.15}', '\\begin{tabular}{@{}l rl rl@{}}', '\\toprule',
         ' & \\multicolumn{2}{c}{Spearman} & \\multicolumn{2}{c}{Partial, given ECI} \\\\',
         '\\cmidrule(lr){2-3}\\cmidrule(l){4-5}', 'Pair & $\\rho$ & 95\\% CI & $\\rho$ & 95\\% CI \\\\', '\\midrule']
for k, p in pairs.items():
    if k == 'Micropolis|FreeCiv': lines.append('\\midrule')
    q = p.get('partial_given_eci')
    lines.append(' & '.join([k.replace('|', '--'), rho_cell(p['spearman']['rho']), ci_cell(p['spearman']['ci']),
                             rho_cell(q['rho']) if q else '--', ci_cell(q['ci']) if q else '']) + ' \\\\')
sim = [p for k, p in pairs.items() if 'partial_given_eci' in p]   # pairs of simulators
ranges = {'SimScoreRho': [p['spearman']['rho'] for p in sim], 'SimScorePartial': [p['partial_given_eci']['rho'] for p in sim]}
macros = ''.join(f'\\newcommand{{\\{k}{end}}}{{{f(v):.2f}}}\n' for k, v in ranges.items() for end, f in (('Lo', min), ('Hi', max)))
outputs = [('simulator_scores_macros.tex', '% Generated by forecastbench-sim-paper/src/fbsim_paper/assets/combined/simulator_scores.py; '
            'do not edit by hand.\n' + macros), ('simulator_scores.json', json_text), ('simulator_correlation_table.tex', '\n'.join(lines + ['\\bottomrule', '\\end{tabular}']) + '\n')]
for name, text in outputs:
    path = DATA / name
    if not path.exists() or path.read_text() != text:
        path.write_text(text); print(f'wrote {path}')
for k, v in pairs.items():
    print(k, {s: f"{x['rho']:+.3f} [{x['ci'][0]:+.2f}, {x['ci'][1]:+.2f}]" for s, x in v.items()})
