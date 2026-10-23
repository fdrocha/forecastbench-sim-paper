#!/usr/bin/env python3
"""Score the paper's baselines on the Micropolis question sets.

Binary: the base rate of the same question at the same horizon in the other
cities. Continuous: the snapshot value plus the other cities' change over the
same horizon, in units of each city's scale. Both leave out the whole city, so
its two snapshots, which share a trunk, never inform each other. Reads only the
gathered paper data; writes one JSON of the three cells' scores.

Usage:
    scripts/micropolis_baselines.py --datadir DIR --out micropolis_baselines.json
"""

import argparse
import csv
import json
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from fbsim_benchmark.scoring.micropolis import (
    PERCENTILE_LEVELS,
    crps_distribution,
    crps_floor,
)
from micropolis_world.continuous_eval import METRIC_RANGES

from fbsim_paper.baselines import base_rates, change_quantiles

sys.path.insert(0, str(Path(__file__).parent))
from analyze_binary import MID_RANGE, TAIL, excess_bits
from gather_paper_data import (
    BINARY_CSV_NAME,
    HISTORY_CSV_NAME,
    REPLAYS_ARCHIVE_NAME,
    SCALES_CSV_NAME,
)
from get_city_scales import METRICS

TURNS_PER_YEAR = 48


def binary(datadir: Path) -> dict:
    items = {}
    for r in csv.DictReader(open(datadir / BINARY_CSV_NAME)):
        items[r["question_id"]] = dict(
            world=r["question_id"].split("_")[0],
            h=r["horizon"],
            qid=r["qid"],
            set=r["section"],
            q=float(r["real_prob"]),
        )
    items = list(items.values())
    question = [lambda it: (it["h"], it["qid"]), lambda it: it["qid"]]
    groups = defaultdict(list)
    for it in items:
        groups[it["h"], it["qid"]].append(it["q"])

    def score(f):
        mid = [(p - it["q"]) ** 2 for p, it in zip(f, items) if it["set"] == MID_RANGE]
        tail = [excess_bits(p, it["q"]) for p, it in zip(f, items) if it["set"] == TAIL]
        return dict(mid=float(np.mean(mid)), tail=float(np.mean(tail)))

    # The paper's base rate and the alternatives the appendix compares it with.
    variants = {
        "simulator": score(base_rates(items, [lambda it: 0])),
        "simulator_horizon": score(base_rates(items, [lambda it: it["h"]])),
        "question": score(base_rates(items, question[1:])),
        "question_horizon": score(base_rates(items, question)),
        "question_horizon_in_sample": score(
            [float(np.mean(groups[it["h"], it["qid"]])) for it in items]
        ),
        "question_horizon_within_set": score(
            base_rates(
                items,
                [lambda it, k=k: (it["set"], k(it)) for k in question]
                + [lambda it: it["set"]],
            )
        ),
        "constant": score([0.5 if it["set"] == MID_RANGE else 0.05 for it in items]),
    }
    paper = variants["question_horizon"]
    # the paper's base rate at each horizon, for the by-horizon table
    rate = base_rates(items, question)
    by_horizon = {
        h: dict(
            mid=float(
                np.mean(
                    [
                        (p - it["q"]) ** 2
                        for p, it in zip(rate, items)
                        if it["h"] == h and it["set"] == MID_RANGE
                    ]
                )
            ),
            tail=float(
                np.mean(
                    [
                        excess_bits(p, it["q"])
                        for p, it in zip(rate, items)
                        if it["h"] == h and it["set"] == TAIL
                    ]
                )
            ),
        )
        for h in sorted({it["h"] for it in items}, key=lambda h: int(h.rstrip("y")))
    }
    return dict(
        mid_range_excess_brier=paper["mid"],
        tail_excess_bits=paper["tail"],
        binary_by_horizon=by_horizon,
        binary_variants=variants,
        n_pool=len(items),
        n_mid_range=sum(it["set"] == MID_RANGE for it in items),
        n_tail=sum(it["set"] == TAIL for it in items),
    )


def continuous(datadir: Path) -> dict:
    history = defaultdict(list)
    for r in csv.DictReader(open(datadir / HISTORY_CSV_NAME)):
        history[r["city"], int(r["snapshot_turn"])].append(
            {m: float(r[m]) for m in METRICS}
        )
    last = {k: v[-1] for k, v in history.items()}
    scales = {
        r["city"]: {m: float(r[m]) for m in METRICS}
        for r in csv.DictReader(open(datadir / SCALES_CSV_NAME))
    }
    items = []
    with tarfile.open(datadir / REPLAYS_ARCHIVE_NAME) as tar:
        for member in tar.getmembers():
            for line in tar.extractfile(member):
                d = json.loads(line)
                for m in METRICS:
                    ys = np.asarray(d["values"][m], float)
                    x0, s = last[d["city"], d["snapshot_turn"]][m], scales[d["city"]][m]
                    items.append(
                        dict(
                            world=d["city"],
                            h=d["horizon"],
                            metric=m,
                            ys=ys,
                            last=x0,
                            scale=s,
                            change=(ys - x0) / s,
                            level=ys / s,
                        )
                    )
    pool = defaultdict(list)
    for it in items:
        pool[it["h"], it["metric"]].append(it)
    taus = list(PERCENTILE_LEVELS.values())
    others = lambda it, key: [
        o[key] for o in pool[it["h"], it["metric"]] if o["world"] != it["world"]
    ]
    # The paper's forecast and the alternatives the appendix compares it with, as quantile functions of a question.
    forecasts = {
        "change": lambda it: change_quantiles(
            it["last"],
            others(it, "change"),
            taus,
            it["scale"],
            *METRIC_RANGES[it["metric"]],
        ),
        "last": lambda it: np.full(len(taus), it["last"]),
        "climatology": lambda it: change_quantiles(
            0.0, others(it, "level"), taus, it["scale"], *METRIC_RANGES[it["metric"]]
        ),
    }
    score = lambda f, it: (
        (crps_distribution(f(it), it["ys"]) - crps_floor(it["ys"])) / it["scale"]
    )
    variants = {
        name: float(np.mean([score(f, it) for it in items]))
        for name, f in forecasts.items()
    }
    # the paper's forecast by horizon ("3y", as the gathered CSVs label it) and by metric, for the continuous table
    paper = {id(it): score(forecasts["change"], it) for it in items}
    by_horizon = {
        f"{h // TURNS_PER_YEAR}y": float(
            np.mean([paper[id(it)] for it in items if it["h"] == h])
        )
        for h in sorted({it["h"] for it in items})
    }
    by_metric = {
        m: float(np.mean([paper[id(it)] for it in items if it["metric"] == m]))
        for m in METRICS
    }
    return dict(
        excess_ncrps=variants["change"],
        continuous_by_horizon=by_horizon,
        continuous_by_metric=by_metric,
        continuous_variants=variants,
        n_continuous=len(items),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--datadir", type=Path, required=True, help="the gathered paper data"
    )
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = dict(
        binary(args.datadir),
        **continuous(args.datadir),
        method=dict(
            binary="mean q of the same question and horizon over the other cities' snapshots, all 3,000 binary questions",
            continuous="snapshot value plus the quantiles of the other cities' change over the same horizon and metric, in units of each city's scale",
        ),
    )
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(
        f"Wrote {args.out}: mid-range {out['mid_range_excess_brier']:.4f}, tail {out['tail_excess_bits']:.4f}, "
        f"continuous {out['excess_ncrps']:.4f}"
    )


if __name__ == "__main__":
    main()
