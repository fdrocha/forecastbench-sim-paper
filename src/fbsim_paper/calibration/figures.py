"""Render the manuscript's two-bar comparison from the recomputed diagnostics."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter


def endpoints(out):
    overview = pd.read_csv(out / 'calibration-overview.csv')
    intervals = pd.read_csv(out / 'cluster-intervals.csv')
    rows = []
    for dataset, horizon, cluster in [('freeciv', 150, 'world'), ('measles', 20, 'year')]:
        point = overview[(overview.dataset == dataset) & (overview.panel == 'available') &
                         (overview.group == 'all') & (overview.horizon == horizon) &
                         (overview.metric == 'central50_upper_miss')]
        ci = intervals[(intervals.dataset == dataset) & (intervals.cluster == cluster) &
                       (intervals.horizon == horizon) & (intervals.metric == 'central50_upper_miss')]
        if len(point) != 1 or len(ci) != 1:
            raise ValueError(f'Expected exactly one endpoint and interval for {dataset}')
        rows.append(dict(evaluation=dataset, rate=float(point.iloc[0].value), horizon=horizon,
                         ci_low=float(ci.iloc[0].ci_low), ci_high=float(ci.iloc[0].ci_high),
                         nominal_upper_bound=.25, interpretation='observed equal-model mean'))
    return pd.DataFrame(rows)


def run(out):
    table = endpoints(out)
    table.to_csv(out / 'calibration_case_study.csv', index=False)
    values, low, high = (table[c].to_numpy() for c in ['rate', 'ci_low', 'ci_high'])
    colors, positions = ['#b74724', '#276b85'], np.array([1, 0])
    with plt.rc_context({'font.family': 'DejaVu Sans', 'font.size': 10, 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False}):
        fig, ax = plt.subplots(figsize=(10.7, 4.25))
        ax.barh(positions, values, height=.5, color=colors, zorder=2)
        ax.errorbar(values, positions, xerr=np.array([values-low, high-values]), fmt='none',
                    ecolor='#263747', capsize=5, lw=1.2, zorder=3)
        ax.axvline(.25, color='#8e979d', ls=(0, (4, 3)), lw=1, zorder=1)
        for i, value in enumerate(values):
            ax.text(high[i]+.025, positions[i], f'{value:.1%}', va='center',
                    fontweight='bold', fontsize=13, color=colors[i])
        ax.set_yticks(positions, ['FreeCiv\n150 turns ahead', 'Historical measles\n20 weeks ahead'])
        ax.set(xlim=(0, 1), ylim=(-.6, 1.6),
               xlabel='Share of outcomes exceeding the predicted 75th percentile')
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.grid(axis='x', alpha=.13)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y', length=0, pad=12)
        fig.subplots_adjust(left=.26, right=.98, top=.95, bottom=.19)
        for ext in ['pdf', 'svg', 'png']:
            metadata = {'CreationDate': None, 'ModDate': None} if ext == 'pdf' else None
            fig.savefig(out / f'calibration_case_study.{ext}', dpi=180, metadata=metadata)
        plt.close(fig)
    # A compact machine-readable check of the named-domain sensitivity.
    context = pd.read_csv(out / 'matched-context.csv')
    context = context[context.horizon == 20]
    summary = {name: dict(models=int(len(group)), rate=float(group.upper_miss.mean()),
                         models_above_nominal=int((group.upper_miss > .25).sum()),
                         min_pairs=int(group.n.min()), max_pairs=int(group.n.max()))
               for name, group in context.groupby('context')}
    (out / 'matched-context-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
