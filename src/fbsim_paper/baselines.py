"""Reference forecasts for the paper's baselines, shared by the three worlds.

Each baseline knows how the same question resolved in the simulator's other worlds, and nothing of
this world's report beyond the quantity's current value.
"""

from collections import defaultdict

import numpy as np


def base_rates(items, keys, world="world", q="q"):
    """Each item's base rate: the mean q of the items sharing its key in the other worlds.

    `keys` are functions of an item, finest first; an item whose key has no item in another world
    falls back to the next.
    """
    out = []
    for key in keys:
        sums = defaultdict(lambda: defaultdict(lambda: [0.0, 0]))
        for it in items:
            s = sums[key(it)][it[world]]; s[0] += it[q]; s[1] += 1
        rates = []
        for it in items:
            others = [s for w, s in sums[key(it)].items() if w != it[world]]
            n = sum(s[1] for s in others)
            rates.append(sum(s[0] for s in others) / n if n else None)
        out.append(rates)
    return [next(r[i] for r in out if r[i] is not None) for i in range(len(items))]


def change_quantiles(last, changes, taus, scale=1.0, lo=None, hi=None):
    """Quantiles at `taus` of last + scale * c, c pooled over the arrays `changes`, clipped to [lo, hi]."""
    q = last + scale * np.quantile(np.concatenate(changes), taus)
    return np.clip(q, -np.inf if lo is None else lo, np.inf if hi is None else hi)
