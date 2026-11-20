"""Run retained-data calibration diagnostics in a new directory, with networking disabled."""
from pathlib import Path
import hashlib
import json
import math
import os
import subprocess
import sys

# Inputs in the data archive, relative to its data/ folder.
FREECIV = 'datasets/freeciv-source/worlds/freeciv/fbsim_v3'
MEASLES = 'datasets/measles-case-study/timeseries'
ROSTER = 'datasets/measles-case-study/measles-roster.json'
# The manuscript files the build delivers, by output file name.
PAPER_FILES = {'calibration_case_study.csv': 'data/calibration_case_study.csv',
               'calibration_case_study.pdf': 'figures/calibration_case_study.pdf'}


def archive_inputs(data):
    """(freeciv_root, measles_root, measles_roster) in the data archive."""
    data = Path(data)
    return data/FREECIV, data/MEASLES, data/ROSTER


def run(freeciv_root, measles_root, measles_roster, output, parser_audit=False):
    fc, ts, roster, out = (Path(p).expanduser().resolve()
                          for p in [freeciv_root, measles_root, measles_roster, output])
    if out.exists():
        raise ValueError('Output must be a new directory; existing analysis is never overwritten')
    required = [fc/'sets/draw_v1/continuous_300.json',
                fc/'results/run2_paper/results_v1/freeciv_results_wide.csv',
                ts/'data/scores', ts/'data/series/measles', roster]
    for p in required:
        if not p.exists():
            raise ValueError(f'Missing input: {p}; this command does not download inputs')
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
    if parser_audit:
        if not (ts/'data/forecasts').is_dir():
            raise ValueError('Parser audit needs the measles replies in data/forecasts')
        if not list((fc/'results/run2b_2026-09-20/batched').glob('*/calls.jsonl.gz')):
            raise ValueError('Parser audit needs the FreeCiv replies (calls.jsonl.gz)')
    out.mkdir(parents=True)
    config = dict(freeciv_root=str(fc), measles_root=str(ts), measles_roster=str(roster),
                  output=str(out), parser_audit=parser_audit)
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
    return dict(status='PASS', output=str(out), parser_audit=parser_audit,
                scope='Retained FreeCiv and historical measles; no providers or simulators')
