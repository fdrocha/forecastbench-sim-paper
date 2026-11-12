"""Held-out worlds and simulators (Appendix C, app:generalization): does the model ranking depend on which worlds and
which simulators the combined score is fitted on?
    python generalization.py --paper-root PAPER --freeciv-scores SCORE_ITEMS

A. Half vs half: split the worlds into two disjoint halves, compute every cell from each half's questions alone, fit
   theta on each half (the additive log-loss model of combined_score.py) and take the Spearman correlation of the two
   fits. 'All three' splits every simulator's worlds at once and fits all nine cells (1,000 random splits, seed 2026);
   the per-simulator rows fit that simulator's cells and use every distinct split (Micropolis 7 vs 8 cities: 6,435;
   FreeCiv 4 vs 4 games: 35; Starsim 2 vs 2 scenarios: 3).
B. Leave one simulator out: theta fitted on two simulators' cells against theta fitted on the held-out simulator's
   cells alone (its simulator-level combined score, as in simulator_scores.py). 95% CI: percentile bootstrap over
   models, 10,000 resamples of default_rng(2026), models in the order of data/freeciv/models_v2.csv; theta is not
   refitted.

A world is a Micropolis city (15), a FreeCiv anchor game (8) or a Starsim beta scenario (4). Every cell score is the
mean of its item scores over the items a model answered (Starsim: missing unless the model answered every item), so a
cell over a set of worlds is the same mean restricted to their items. The script checks that pooling all worlds
refits data/combined_score.json before it splits anything.

Reads the manuscript's data/ (model_names.csv, freeciv/models_v2.csv, the Micropolis forecast CSVs, Starsim's
fixed-state item scores, combined_score.json) and FreeCiv's per-item scores from the data archive
(datasets/freeciv-source/worlds/freeciv/fbsim_v3/results/run2_paper/scores_v1/score_items.csv.gz). Writes
data/generalization.json, data/generalization_table.tex and data/generalization_macros.tex.
"""
import argparse, csv, json
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('--paper-root', type=Path, required=True)
ap.add_argument('--freeciv-scores', type=Path, required=True, help='FreeCiv run2_paper scores_v1/score_items.csv.gz')
args = ap.parse_args()
DATA = args.paper_root.resolve() / 'data'
SCRIPT = 'forecastbench-sim-paper/src/fbsim_paper/assets/combined/generalization.py'

SIMS = ['Micropolis', 'FreeCiv', 'Starsim']
CELLS = [('Micropolis', 'mid-range excess Brier'), ('Micropolis', 'tail excess bits'), ('Micropolis', 'excess nCRPS'),
         ('Starsim', 'continuous excess CRPS'), ('Starsim', 'interventional excess CRPS'),
         ('FreeCiv', 'mid-range excess Brier'), ('FreeCiv', 'tail excess bits'), ('FreeCiv', 'excess nCRPS'),
         ('FreeCiv', 'natural-conditional excess Brier')]   # the order of combined_score.py's nine cells
COMPLETE = {('Starsim', 'continuous excess CRPS'), ('Starsim', 'interventional excess CRPS')}

SHORT = {r['model']: r['short_name'] for r in csv.DictReader(open(DATA / 'model_names.csv'))}
ECI = {SHORT.get(r['openrouter_id'], r['name']): float(r['eci']) for r in csv.DictReader(open(DATA / 'freeciv/models_v2.csv'))}
MODELS = list(ECI)   # this order fixes the bootstrap resamples


def items():
    """One row per (cell, model, item): the cell, the model's short name, the item's world and its score."""
    parts = []
    b = pd.read_csv(DATA / 'micropolis/binary_forecasts.csv')
    b['world'] = b.question_id.str.split('_').str[0]
    for section, col, cell in (('mid-range', 'excess_brier', CELLS[0]), ('tail', 'excess_bits', CELLS[1])):
        d = b[b.section == section]
        parts.append(pd.DataFrame(dict(cell=[cell] * len(d), model=d.model, world=d.world, item=d.question_id, score=d[col])))
    c = pd.read_csv(DATA / 'micropolis/continuous_forecasts.csv')
    scale = pd.read_csv(DATA / 'micropolis/city_metric_scales.csv').set_index('city')
    c['scale'] = [scale.loc[ci, me] for ci, me in zip(c.city, c.metric)]
    parts.append(pd.DataFrame(dict(cell=[CELLS[2]] * len(c), model=c.model, world=c.city, item=c.question_id,
                                   score=c.excess_crps / c.scale)))
    s = pd.read_csv(args.freeciv_scores, low_memory=False)
    for st, col, cell in (('bank', 'excess_brier', CELLS[5]), ('tails', 'excess_bits', CELLS[6]),
                          ('continuous', 'excess_ncrps_global', CELLS[7]), ('natcond', 'excess_t2', CELLS[8])):
        d = s[s.set == st]
        parts.append(pd.DataFrame(dict(cell=[cell] * len(d), model=d.model, world=d.world, item=d['item'], score=d[col])))
    it = pd.read_csv(DATA / 'starsim/fixed_state/item_scores.csv')
    it['world'] = it['item'].str.split('_').str[0]
    for d, cell in ((it[it.source == 'cont_uncond'], CELLS[3]), (it[it.source.str.startswith('cont_int_')], CELLS[4])):
        parts.append(pd.DataFrame(dict(cell=[cell] * len(d), model=d.model, world=d.world, item=d.source + ':' + d['item'],
                                       score=d.new_excess)))
    df = pd.concat(parts, ignore_index=True)
    df['model'] = df.model.map(lambda m: SHORT.get(m, m))
    return df[np.isfinite(df.score)]   # unparsed items are left out of the means, as in the paper


class Cell:
    """Per-world sums of item scores and item counts, models x worlds; a cell over a multiset of worlds (k_w copies of
    world w) is sum_w k_w S[m, w] / sum_w k_w N[m, w], missing for Starsim unless every item was answered."""

    def __init__(self, df, cell):
        d = df[df.cell == cell]
        self.worlds = sorted(d.world.unique())
        g = d.groupby(['model', 'world']).score
        self.S = g.sum().unstack().reindex(index=MODELS, columns=self.worlds).fillna(0).to_numpy(float)
        self.N = g.size().unstack().reindex(index=MODELS, columns=self.worlds).fillna(0).to_numpy(float)
        self.T = d.groupby('world')['item'].nunique().reindex(self.worlds).to_numpy(float)
        self.complete = cell in COMPLETE

    def pooled(self, keep=None):
        k = np.ones(len(self.worlds)) if keep is None else np.isin(self.worlds, keep).astype(float)
        num, den = self.S @ k, self.N @ k
        out = np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)
        return np.where(den < self.T @ k - 1e-9, np.nan, out) if self.complete else out


def fit(L, iters=500):
    """theta of log l_mc = delta_c - theta_m, alternating means, centered; higher is better (as combined_score.py)."""
    X = np.log(np.maximum(L, 1e-4)); theta = np.zeros(len(L))
    for _ in range(iters):
        delta = np.nanmean(X + theta[:, None], axis=0)
        theta = np.nanmean(delta[None, :] - X, axis=1); theta -= theta.mean()
    return theta


def spearman(x, y):
    ok = np.isfinite(x) & np.isfinite(y)
    return float(stats.spearmanr(x[ok], y[ok]).statistic) if ok.sum() >= 4 else np.nan


df = items()
T = {c: Cell(df, c) for c in CELLS}
L0 = np.column_stack([T[c].pooled() for c in CELLS])
combined = json.load(open(DATA / 'combined_score.json'))['theta']
gap = np.abs(fit(L0) - [combined[m] for m in MODELS]).max()
assert gap < 1e-12, f'pooling every world does not refit combined_score.json (max |difference| {gap:.2e})'
WORLDS = {s: T[next(c for c in CELLS if c[0] == s)].worlds for s in SIMS}


def theta_on(keep, sims):
    """theta fitted on the cells of `sims`, each from the questions of its simulator's worlds in `keep` only."""
    cells = [c for c in CELLS if c[0] in sims]
    return fit(np.column_stack([T[c].pooled(keep[c[0]]) for c in cells]))


def summary(r, per_half):
    r = np.asarray(r)
    return dict(n_splits=len(r), worlds_per_half=per_half, mean=float(r.mean()), median=float(np.median(r)),
                min=float(r.min()), max=float(r.max()))


# A. half vs half
half, rng, r_all = {}, np.random.default_rng(2026), []
for _ in range(1000):
    A, B = {}, {}
    for s, W in WORLDS.items():
        p = rng.permutation(W)
        h = len(W) // 2 + (rng.random() < 0.5 if len(W) % 2 else 0)
        A[s], B[s] = list(p[:h]), list(p[h:])
    r_all.append(spearman(theta_on(A, SIMS), theta_on(B, SIMS)))
half['All three'] = summary(r_all, '7--8 + 4 + 2')
for s in SIMS:
    W, k, rs, seen = WORLDS[s], len(WORLDS[s]) // 2, [], set()
    for a in combinations(W, k):
        b = tuple(w for w in W if w not in a)
        if frozenset([a, b]) in seen: continue
        seen.add(frozenset([a, b]))
        rs.append(spearman(theta_on({s: list(a)}, [s]), theta_on({s: list(b)}, [s])))
    half[s] = summary(rs, f'{k} vs {len(W) - k}')

# B. leave one simulator out
loso, rng = {}, np.random.default_rng(2026)
idx = [rng.integers(0, len(MODELS), len(MODELS)) for _ in range(10000)]
for s in SIMS:
    rest = fit(L0[:, [i for i, c in enumerate(CELLS) if c[0] != s]])
    held = fit(L0[:, [i for i, c in enumerate(CELLS) if c[0] == s]])
    boot = [spearman(rest[i], held[i]) for i in idx]
    loso[s] = dict(fitted_on=[x for x in SIMS if x != s], rho=spearman(rest, held),
                   ci=[float(v) for v in np.nanpercentile(boot, [2.5, 97.5])])

f2 = lambda x: f'{x:.2f}'
thousands = lambda n: f'{n:,}'.replace(',', '{,}')
header = f'% Generated by {SCRIPT}; do not edit by hand.\n'
rows_a = [f"{lab} & {half[k]['worlds_per_half']} & {thousands(half[k]['n_splits'])} & {f2(half[k]['mean'])} & "
          f"{f2(half[k]['min'])}--{f2(half[k]['max'])} \\\\"
          for k, lab in (('All three', 'All three (nine cells)'), ('Micropolis', 'Micropolis'), ('FreeCiv', 'FreeCiv'), ('Starsim', 'Starsim'))]
rows_b = [f"{s} & {' + '.join(v['fitted_on'])} & & {f2(v['rho'])} & [{f2(v['ci'][0])}, {f2(v['ci'][1])}] \\\\" for s, v in loso.items()]
table = header + '\n'.join([
    '\\setlength{\\tabcolsep}{5pt}', '\\begin{tabular}{@{}l l r r l@{}}', '\\toprule',
    '\\multicolumn{5}{@{}l}{\\emph{(a) Half vs half: $\\theta_m$ fitted on two disjoint halves of the worlds}} \\\\',
    'Worlds split & Worlds per half & Splits & Mean $\\rho$ & Min--max \\\\', '\\midrule', *rows_a, '\\midrule',
    '\\multicolumn{5}{@{}l}{\\emph{(b) Leave one simulator out: $\\theta_m$ fitted on two simulators vs the third}} \\\\',
    'Held-out simulator & Fitted on & & $\\rho$ & 95\\% CI \\\\', '\\midrule', *rows_b, '\\bottomrule', '\\end{tabular}']) + '\n'
rhos = [v['rho'] for v in loso.values()]
macros = dict(GenHalfRho=f2(half['All three']['mean']), GenHalfMin=f2(half['All three']['min']),
              GenHalfSplits=thousands(half['All three']['n_splits']), GenHalfMicropolis=f2(half['Micropolis']['mean']),
              GenHalfFreeCiv=f2(half['FreeCiv']['mean']), GenHalfStarsim=f2(half['Starsim']['mean']),
              GenLosoLo=f2(min(rhos)), GenLosoHi=f2(max(rhos)))
outputs = [('generalization_table.tex', table),
           ('generalization_macros.tex', header + ''.join(f'\\newcommand{{\\{k}}}{{{v}}}\n' for k, v in macros.items())),
           ('generalization.json', json.dumps(dict(script=SCRIPT, n_models=len(MODELS), worlds=WORLDS, half_vs_half=half,
                                                   leave_one_simulator_out=loso), indent=1) + '\n')]
for name, text in outputs:
    path = DATA / name
    if not path.exists() or path.read_text() != text:
        path.write_text(text); print(f'wrote {path}')
for k, v in half.items():
    print(f"half vs half {k:10s}: {v['n_splits']:5d} splits ({v['worlds_per_half']}), mean {v['mean']:.3f}, min {v['min']:.3f}, max {v['max']:.3f}")
for s, v in loso.items():
    print(f"leave out {s:10s}: rho {v['rho']:.3f} [{v['ci'][0]:.2f}, {v['ci'][1]:.2f}]")
