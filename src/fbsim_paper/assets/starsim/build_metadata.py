"""Update the Starsim reasoning-token column of the paper's roster table, preserving the other columns.

Read each of the seven source sets once (pooled over horizons, not pooled over rungs).
Costs cover recorded successful scored calls, not total provider billing or failed attempts.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

SETS = [
    ('binary', 'interventional', 'c90'), ('binary', 'interventional', 'hold'),
    ('binary', 'unconditional', '-'), ('continuous', 'interventional', 'c25'),
    ('continuous', 'interventional', 'c50'), ('continuous', 'interventional', 'c90'),
    ('continuous', 'unconditional', '-'),
]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--paper-root', type=Path, required=True)
parser.add_argument('--csv', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
models = defaultdict(dict)
for row in csv.DictReader(args.csv.open()):
    key = (row['question_type'], row['condition'], row['rung'])
    if row['horizon'] == 'pooled' and key in SETS:
        assert key not in models[row['model']], (row['model'], key)
        models[row['model']][key] = row
assert len(models) == 24, 'Unexpected roster; review paper templates before replacing columns.'
summary = {}
by_eci = {}
for model, cells in models.items():
    assert set(cells) == set(SETS), (model, 'missing source set')
    calls = sum(int(r['n_calls']) for r in cells.values())
    cost = sum(float(r['cost_usd']) for r in cells.values())
    tokens = sum(int(r['n_calls']) * float(r['reasoning_tokens_mean']) for r in cells.values()) / calls
    eci = round(float(next(iter(cells.values()))['eci']), 2)
    assert eci not in by_eci, 'ECI collision; use an explicit name mapping.'
    by_eci[eci] = model
    summary[model] = dict(calls=calls, cost_usd=cost, reasoning_tokens_mean=tokens)

def read_rows(path):
    return path.read_text().splitlines()

def cells_of(line):
    return [x.strip() for x in line.removesuffix(' \\\\').split('&')]

def table_row(cells):
    return ' & '.join(cells) + r' \\'

# Read exact ECI values in the existing roster to establish a checked display-name join.
roster = read_rows(args.paper_root / 'data/roster_table.tex')
name_to_model = {}
for i, line in enumerate(roster):
    if '&' not in line or not line.endswith(r'\\'):
        continue
    cells = cells_of(line)
    try:
        eci = float(cells[1])
    except ValueError:
        continue
    model = by_eci[eci]
    assert model not in name_to_model.values()
    name_to_model[cells[0]] = model
    cells[-1] = f"{summary[model]['reasoning_tokens_mean']:,.0f}"
    roster[i] = table_row(cells)
assert set(name_to_model.values()) == set(models)
(args.out / 'roster_table.tex').write_text('\n'.join(roster) + '\n')

result = dict(calls=sum(x['calls'] for x in summary.values()),
              cost_usd=sum(x['cost_usd'] for x in summary.values()),
              zero_reasoning_models=sum(x['reasoning_tokens_mean'] == 0 for x in summary.values()),
              accounting='Recorded successful scored calls only; excludes failed/unrecorded attempts.',
              models=summary)
(args.out / 'metadata_summary.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'models'}, indent=2))
