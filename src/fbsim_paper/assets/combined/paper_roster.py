"""The model panel as the combined-score scripts read it, from the paper checkout alone."""
import csv
from pathlib import Path


def paper_roster(paper_root):
    """The panel in roster order, as (models, ECI by short name, short name by model id).

    data/freeciv/models_v2.csv gives the order and ECI, data/model_names.csv the short names.
    """
    root = Path(paper_root)
    with open(root / 'data' / 'model_names.csv') as f:
        short = {r['model']: r['short_name'] for r in csv.DictReader(f)}
    with open(root / 'data' / 'freeciv' / 'models_v2.csv') as f:
        eci = {short.get(r['openrouter_id'], r['name']): float(r['eci']) for r in csv.DictReader(f)}
    return list(eci), eci, short
