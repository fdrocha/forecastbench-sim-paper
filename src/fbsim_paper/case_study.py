"""Run retained-data calibration diagnostics in a new directory, with networking disabled."""
from pathlib import Path
import hashlib
import json
import math
import os
import subprocess
import sys


def run(freeciv_root, measles_root, measles_roster, output, raw_repo=None,
        raw_ref='daca5a15af759f4124960e30694bff15256b7f5d'):
    fc, ts, roster, out = (Path(p).expanduser().resolve()
                          for p in [freeciv_root, measles_root, measles_roster, output])
    if out.exists():
        raise ValueError('Output must be a new directory; existing analysis is never overwritten')
    required = [fc/'sets/draw_v1/continuous_300.json',
                fc/'results/run2_paper/results_v1/freeciv_results_wide.csv',
                ts/'data/scores', ts/'data/series/measles', roster]
    for p in required:
        if not p.exists():
            raise ValueError(f'Missing private input: {p}; this command does not download inputs')
    if not list((fc/'results/run2b_2026-09-20/batched').glob('*/results.jsonl')):
        raise ValueError('No FreeCiv retained forecast files')
    if not list((ts/'data/scores').glob('*.csv')):
        raise ValueError('No measles score files')
    if any(out.is_relative_to(p) for p in [fc, ts, roster.parent]):
        raise ValueError('Output must be outside the input directories')
    # Outputs include private item-level arrays and parser excerpts, never write them into a Git tree.
    if any((p/'.git').exists() for p in [out, *out.parents]):
        raise ValueError('Output must be outside Git checkouts because it contains private data')
    scores = json.loads(roster.read_text())
    if not isinstance(scores, dict) or not scores or not all(
            isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for k, v in scores.items()):
        raise ValueError('Measles roster must be a JSON object mapping model IDs to ECI scores')
    if raw_repo is not None:
        raw_repo = Path(raw_repo).expanduser().resolve()
        if not (ts/'data/forecasts').is_dir():
            raise ValueError('Parser audit needs retained measles data/forecasts')
        subprocess.run(['git', '-C', str(raw_repo), 'cat-file', '-e', raw_ref+'^{commit}'], check=True)
    out.mkdir(parents=True)
    config = dict(freeciv_root=str(fc), measles_root=str(ts), measles_roster=str(roster),
                  output=str(out), raw_repo=str(raw_repo) if raw_repo else None, raw_ref=raw_ref)
    # This receipt is private, like every output of this command.
    (out/'run-config.json').write_text(json.dumps(config, indent=2)+'\n')
    (out/'roster-provenance.json').write_text(json.dumps(
        dict(sha256=hashlib.sha256(roster.read_bytes()).hexdigest()), indent=2)+'\n')
    code = Path(__file__).parent
    hashes = {str(p.relative_to(code)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [Path(__file__), *sorted((code/'calibration').glob('*.py'))]}
    (out/'analysis-source-hashes.json').write_text(json.dumps(hashes, indent=2)+'\n')
    guard = code/'assets/offline'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', MPLCONFIGDIR=str(out/'mpl'), MPLBACKEND='Agg')
    env['PYTHONPATH'] = str(guard)+os.pathsep+os.pathsep.join(sys.path)
    subprocess.run([sys.executable, '-m', 'fbsim_paper.calibration', str(out/'run-config.json')],
                   env=env, check=True)
    return dict(status='PASS', output=str(out), parser_audit=raw_repo is not None,
                scope='Retained FreeCiv and historical measles; no providers or simulators')
