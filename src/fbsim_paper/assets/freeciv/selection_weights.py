#!/usr/bin/env python3
"""Selection weights of the FreeCiv mid-range questions, for the appendix's comparison with equal weights.

    python selection_weights.py --sets SETS_DIR --fractions selection_fractions_bank_tails_mirrors.json --out OUT.csv

A question's weight is n_pool / n_selected of its (band, horizon, family) group in Jaeho Lee's selection fractions,
rescaled so that each (family, horizon) keeps its number of questions: it undoes the selection on q within each family
and horizon and keeps the drawn mix of families.  The fractions file counts the q = 0.95 question that band 4 shares
with the mirrors in band 4, so the bank's own selected counts are used.
"""
import argparse, ast, collections, csv, json

BANDS = [(0.05, 0.23), (0.23, 0.41), (0.41, 0.59), (0.59, 0.77), (0.77, 0.95)]   # as draw_v1.py: lo < q <= hi

ap = argparse.ArgumentParser()
ap.add_argument("--sets", required=True, help="the draw's question sets (sets/draw_v1)")
ap.add_argument("--fractions", required=True, help="selection_fractions_bank_tails_mirrors.json")
ap.add_argument("--out", required=True)
a = ap.parse_args()

frac = {ast.literal_eval(k): v for k, v in json.load(open(a.fractions)).items()}
qs = json.load(open(f"{a.sets}/bank_750.json"))
band = {c["id"]: next(i for i, (lo, hi) in enumerate(BANDS) if lo < c["qAll"] <= hi) for c in qs}
group = {c["id"]: (band[c["id"]], c["T"], c["family"]) for c in qs}
n_sel = collections.Counter(group.values())
differ = {g: (frac[g]["n_selected"], n) for g, n in n_sel.items() if frac[g]["n_selected"] != n}
assert differ == {(4, 180, "NB1_threshold"): (3, 2)}, differ
raw = {i: frac[g]["n_pool"] / n_sel[g] for i, g in group.items()}
cells = collections.defaultdict(list)
for c in qs:
    cells[(c["family"], c["T"])].append(c["id"])
w = {i: raw[i] * len(ids) / sum(raw[j] for j in ids) for ids in cells.values() for i in ids}

with open(a.out, "w", newline="") as f:
    wr = csv.DictWriter(f, fieldnames=["item", "world", "family", "T", "q", "band", "n_pool", "n_selected", "w"])
    wr.writeheader()
    for c in qs:
        g = group[c["id"]]
        wr.writerow(dict(item=c["id"], world=c["world"], family=c["family"], T=c["T"], q=c["qAll"], band=g[0],
                         n_pool=frac[g]["n_pool"], n_selected=n_sel[g], w=w[c["id"]]))
ws = list(w.values())
print(f"{len(qs)} mid-range questions in {len(n_sel)} groups ({sum(frac[g]['n_pool'] for g in n_sel):,} candidates); "
      f"weights {min(ws):.3f} to {max(ws):.3f}, effective number {sum(ws) ** 2 / sum(x * x for x in ws):.0f}")
print("wrote", a.out)
