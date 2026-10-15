"""Install only the current generated Starsim/combined outputs into a local paper checkout.

No prose migrations, git commands, or network operations. Other worlds' validation rows are retained.
"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--from-dir', type=Path, required=True)
parser.add_argument('--paper-root', type=Path, required=True)
a = parser.parse_args()
outputs = {
    'starsim_excess_long.csv': 'data/starsim/starsim_excess_long.csv',
    'per_item_table.tex': 'data/starsim/per_item_table.tex',
    'combined_score.json': 'data/combined_score.json',
    'combined_score_table.tex': 'data/combined_score_table.tex',
    'roster_table.tex': 'data/roster_table.tex',
    'hosting_cost_table.tex': 'data/hosting_cost_table.tex',
    'cost_per_item.tex': 'data/appendix_tables/cost_per_item.tex',
}
for name in ('starsim_models', 'starsim_horizon', 'starsim_rung_horizon'):
    outputs[name + '.tex'] = 'data/appendix_tables/' + name + '.tex'
for name in ('fig_starsim_unconditional', 'fig_starsim_interventional', 'fig_starsim_horizon', 'fig_combined_score'):
    outputs[name + '.pdf'] = 'figures/' + name + '.pdf'
outputs['fig_combined_score.json'] = 'figures/fig_combined_score.json'
# Read and validate all inputs before writing anything.
pending = {a.paper_root / dst: (a.from_dir / src).read_bytes() for src, dst in outputs.items()}
for name, rows in json.loads((a.from_dir / 'validation_rows.json').read_text())['rows'].items():
    p = a.paper_root / 'data' / name
    lines = p.read_text().splitlines()
    hits = [i for i, line in enumerate(lines) if line.startswith(r'\multirow{3}{*}{Starsim}')]
    assert len(hits) == 1 and len(rows) == 3, p
    start = hits[0]
    assert all('&' in line for line in lines[start:start + 3]), p
    lines[start:start + 3] = rows
    if lines[0].startswith('% Starsim rows'):
        lines[0] = '% Starsim rows: data/starsim/scripts/build_excess_extra.py; excess scores; model-bootstrap seed 0 for ECI, 2026 for ForecastBench. Other worlds retained.'
    lines = [line.replace('10,000 resamples, seed 2026)', '10,000 resamples, seed 2026 except Starsim ECI: seed 0)') if line.startswith('% Axis:') else line for line in lines]
    pending[p] = ('\n'.join(lines) + '\n').encode()
for path, data in pending.items():
    if not path.exists() or path.read_bytes() != data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(path.relative_to(a.paper_root))
