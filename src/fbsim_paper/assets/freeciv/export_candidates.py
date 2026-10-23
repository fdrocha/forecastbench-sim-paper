#!/usr/bin/env python3
"""Export the generator's FreeCiv candidates from the per-world bank pickles, for the base-rate baselines.

    python export_candidates.py --bank BANK_V1_DIR --sets SETS_DIR --out OUT_DIR

Run once, by hand, on the bank_v1/<world>.pkl files of draw/bank_v1.py (not in the archive); the build reads its
outputs. Writes binary_candidates.csv (every binary candidate with 0 < q < 1, the draw's pool) and
continuous_candidates.npz (every continuous candidate the draw could pick: count and value families with a positive
replay median and interquartile range, with its 1,000 replay values). Ids are the draw's, <world>:b<i> and
<world>:c<i>; the asked questions are checked against them.
"""
import argparse, csv, json, pickle
from pathlib import Path
import numpy as np

PARAMS = ("k", "metric", "gov", "tech", "wonder", "kind", "f")
DRAWN = {"P1_civ_conquests", "P2_civ_losses", "P3_civ_founds", "P5_techs_at_T", "P6_world_techs", "NC5_world_captures",
         "NC14_world_wonders", "S7_world_razings", "NC1_value_at_T"}   # draw_v1.py: COUNT_FAMS and value questions

ap = argparse.ArgumentParser()
ap.add_argument("--bank", type=Path, required=True, help="the bank_v1 pickles")
ap.add_argument("--sets", type=Path, required=True, help="the draw's question sets (sets/draw_v1)")
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)

W = {f.stem: pickle.load(open(f, "rb")) for f in sorted(a.bank.glob("*.pkl"))}
binary = [dict(id=f"{w}:b{i}", world=w, family=c["family"], T=c["T"], **{p: c.get(p, "") for p in PARAMS},
               subj=" ".join(c["subj"]), q=c["qAll"], text=c["text"])
          for w, D in W.items() for i, c in enumerate(D["bin"]) if 0 < c["qAll"] < 1]
cont = [(f"{w}:c{i}", w, c, D["V"][i]) for w, D in W.items() for i, c in enumerate(D["cont"])
        if c["family"] in DRAWN and c["iqrAll"] > 0 and c["medAll"] > 0]

# the asked questions must be candidates, with the same text and truth
by = {c["id"]: c for c in binary}
asked = [it for n in ("bank_750", "tails_300", "mirrors_50", "natcond_extra_turn1") for it in json.load(open(a.sets / f"{n}.json"))]
assert all(by[it["id"]]["text"] == it["text"] and by[it["id"]]["q"] == it["qAll"] for it in asked)
cby = {i: v for i, _, _, v in cont}
assert all(np.array_equal(cby[it["id"]], np.asarray(it["values"], float)) for it in json.load(open(a.sets / "continuous_300.json")))

with open(a.out / "binary_candidates.csv", "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=list(binary[0]))
    wr.writeheader(); wr.writerows(binary)
np.savez_compressed(a.out / "continuous_candidates.npz", id=[i for i, *_ in cont], world=[w for _, w, *_ in cont],
                    family=[c["family"] for _, _, c, _ in cont], metric=[c.get("metric", "") for _, _, c, _ in cont],
                    T=[c["T"] for _, _, c, _ in cont], subj=[" ".join(c["subj"]) for _, _, c, _ in cont],
                    values=np.array([v for *_, v in cont], dtype=float))
print(f"{len(binary)} binary and {len(cont)} continuous candidates; all {len(asked)} asked binary and 300 continuous questions match")
