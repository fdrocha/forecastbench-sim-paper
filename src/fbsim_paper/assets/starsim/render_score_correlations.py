"""Render only the two Starsim ECI figures from accepted scores and saved intervals.

Example (existing analysis environment, no simulations or bootstrap reruns):
  PYTHONDONTWRITEBYTECODE=1 python render_score_correlations.py \
    --analysis-root /path/to/iclr-2026 --paper-root /path/to/paper --out /path/to/output

The raw rho_ci interface used by build_excess is retained. Continuous intervals
come from fixed_state/associations.csv (2,000 paired model resamples); the binary
interval comes from integration_numbers.json (original 10,000 model resamples).
This entrypoint never refits the combined score, rescores forecasts or writes inputs.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import numpy as np
from scipy.stats import spearmanr


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--analysis-root', type=Path, required=True)
    ap.add_argument('--paper-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    # Import initialization resolves the explicitly supplied analysis checkout.
    import build_excess as be
    root = args.paper_root.resolve() / 'data/starsim'
    paths = [root/'starsim_excess_long.csv', root/'fixed_state/associations.csv', root/'integration_numbers.json']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    rows = list(csv.DictReader(paths[0].open()))
    for r in rows:
        r['complete'] = r['complete'] == 'True'
        for k in ('eci', 'excess'):
            if r[k]: r[k] = float(r[k])
            else: r.pop(k)
        if r['horizon'] != 'pooled': r['horizon'] = int(r['horizon'])
    ass = {(r['group'], r['against']): r for r in csv.DictReader(paths[1].open()) if r['horizon'] == 'pooled'}
    binary = json.loads(paths[2].read_text())['starsim']['validation']['Excess bits, binary']['eci']
    groups = [('binary_uncond', 'binary', 'unconditional', '-'),
              ('cont_uncond', 'continuous', 'unconditional', '-'),
              ('interventional_pooled', 'continuous', 'interventional', 'pooled(c25,c50,c90)')]
    groups += [('cont_int_'+c, 'continuous', 'interventional', c) for c in ('c25','c50','c90')]
    lookup = {}; evidence = []
    for name, typ, cond, rung in groups:
        pts = be.series(rows, typ, cond, rung)
        full = [p for p in pts if p[3]]
        raw = float(spearmanr([p[1] for p in full], [p[2] for p in full]).statistic)
        if name == 'binary_uncond':
            r, lo, hi, n = (binary[k] for k in ('rho','lo','hi','n'))
        else:
            s = ass[name,'eci']; r,lo,hi,n = -float(s['new_skill_rho']),-float(s['new_panel_hi']),-float(s['new_panel_lo']),int(s['n'])
        assert math.isclose(raw, r, abs_tol=1e-12), (name,raw,r)
        assert len(full) == n
        key = tuple((p[0], p[1], p[2], p[3]) for p in pts)
        lookup[key] = r, lo, hi, n
        adjusted = float(spearmanr([p[1] for p in full], [-p[2] for p in full]).statistic)
        assert math.isclose(adjusted, -raw, abs_tol=1e-12)
        assert math.isclose(hi-lo, (-lo)-(-hi), abs_tol=1e-15)
        evidence.append(dict(group=name,raw=[r,lo,hi],display=[-r,-hi,-lo],n=n,coordinates=pts))
    def saved_raw_interval(points, *args, **kwargs):
        return lookup[tuple((p[0],p[1],p[2],p[3]) for p in points)]
    be.fg.rho_ci = saved_raw_interval
    args.out.mkdir(parents=True, exist_ok=True)
    be.fig_unconditional(rows, args.out, {40:200.,60:300.})
    be.fig_interventional(rows, args.out)
    assert hashes == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (args.out/'sign_render_evidence.json').write_text(json.dumps({'inputs':hashes,'panels':evidence},indent=2)+'\n')
    print('PASS: six panels, saved intervals, unchanged scores/coordinates and normalization; no resampling.')


if __name__ == '__main__':
    main()
