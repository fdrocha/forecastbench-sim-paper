"""Partial Spearman correlation of each of the nine scores with ForecastBench overall, ECI partialled out (Appendix C).
    python partial_correlations.py --paper-root PAPER

Writes data/validation_partial_forecastbench.json, read by make_validation_tables.py. Sign-adjusted so that positive
means higher ForecastBench, better score, at equal ECI; CI is the 95% percentile bootstrap over the 17 models
(10,000 resamples, seed 2026); p is the t approximation on n - 3 degrees of freedom.
"""
import argparse, json, runpy, sys
from pathlib import Path
import numpy as np
from scipy import stats

RESAMPLES, SEED = 10000, 2026


def partial_spearman(x, y, z):
    """Pearson correlation of the ranks of x and y after regressing each on the ranks of z; NaN if either is a
    linear function of z's ranks (residuals within rounding of zero)."""
    rx, ry, rz = (stats.rankdata(v) for v in (x, y, z))
    D = np.column_stack([np.ones_like(rz), rz])
    ex = rx - D @ np.linalg.lstsq(D, rx, rcond=None)[0]
    ey = ry - D @ np.linalg.lstsq(D, ry, rcond=None)[0]
    return float(np.corrcoef(ex, ey)[0, 1]) if ex.std() > 1e-9 * rx.std() and ey.std() > 1e-9 * ry.std() else np.nan


def partial_with_ci(x, y, z, idx=None):
    """Point, 95% percentile interval over idx (model resamples) and t-approximation p."""
    x, y, z = (np.asarray(v, float) for v in (x, y, z)); n = len(x)
    if idx is None:
        idx = np.random.default_rng(SEED).integers(0, n, (RESAMPLES, n))
    r = partial_spearman(x, y, z)
    draws = np.array([partial_spearman(x[i], y[i], z[i]) for i in idx])
    lo, hi = map(float, np.nanquantile(draws, [.025, .975]))
    t = r * np.sqrt((n - 3) / max(1e-12, 1 - r * r))
    return dict(n=n, rho=r, ci_lo=lo, ci_hi=hi, p=float(2 * stats.t.sf(abs(t), n - 3)),
                n_boot_valid=int(np.isfinite(draws).sum()))


def load_cells(paper):
    """The nine per-model loss cells, models, ECI and ForecastBench overall, as combined_score.py reads them."""
    here = Path(__file__).resolve().parent
    argv, path = sys.argv, list(sys.path)
    sys.path.insert(0, str(here)); sys.argv = ['combined', '--paper-root', str(paper), '--out', '/dev/null']
    try:
        g = runpy.run_path(str(here / 'combined_score.py'), run_name='integration_import')
        cells = {}
        for src in [g['MICRO'], g['starsim']('excess'), g['FREE']]:
            for k in next(iter(src.values())):
                cells[k] = {m: src[m][k] for m in g['MODELS']}
    finally:
        sys.argv, sys.path[:] = argv, path
    roster = json.loads((paper / 'data/starsim/fixed_state/roster.json').read_text())
    fb = {g['SHORT'][r['openrouter_id']]: r['fb_overall'] for r in roster}
    return cells, g['MODELS'], g['ECI'], fb


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--paper-root', type=Path, required=True)
    P = ap.parse_args().paper_root.resolve()
    cells, models, eci, fb = load_cells(P)
    out = dict(script='forecastbench-sim-paper/src/fbsim_paper/assets/combined/partial_correlations.py',
               method='Spearman partial: Pearson of rank residuals on rank(ECI); rho(FB, -loss | ECI); '
                      f'{RESAMPLES:,} model resamples, seed {SEED}; p from t on n-3 df', rows={})
    for label, vals in cells.items():
        ms = [m for m in models if fb[m] is not None and vals[m] is not None]
        x = [fb[m] for m in ms]; y = [-vals[m] for m in ms]; z = [eci[m] for m in ms]
        out['rows'][label] = dict(bivariate_rho=float(stats.spearmanr(x, y).statistic), **partial_with_ci(x, y, z))
        r = out['rows'][label]
        print(f"{label:45s} n={r['n']} rho={r['bivariate_rho']:+.3f} partial={r['rho']:+.3f} "
              f"[{r['ci_lo']:+.2f}, {r['ci_hi']:+.2f}] p={r['p']:.3f}")
    path = P / 'data/validation_partial_forecastbench.json'
    text = json.dumps(out, indent=1) + '\n'
    if not path.exists() or path.read_text() != text:
        path.write_text(text); print(f'wrote {path}')
