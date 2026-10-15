import argparse, re, pathlib, sys
ap = argparse.ArgumentParser()
ap.add_argument("--paper-root", type=pathlib.Path, required=True)
ROOT = ap.parse_args().paper_root
files = ["sections/06_starsim.tex","sections/09_discussion.tex","appendix/C_full_results.tex","appendix/D_ablations.tex","sections/07_validation.tex","sections/03_benchmark_design.tex","sections/02_introduction.tex","sections/01_abstract.tex","data/starsim/per_item_table.tex","data/appendix_tables/starsim_models.tex","data/appendix_tables/starsim_horizon.tex","data/appendix_tables/starsim_rung_horizon.tex","data/validation_table.tex","data/validation_table_main.tex","data/validation_table_forecastbench.tex"]
labels = set()
for p in ROOT.rglob("*.tex"): labels |= set(re.findall(r"\\label\{([^}]+)\}", p.read_text()))
ok = True
for f in files:
    s = (ROOT / f).read_text(); body = "\n".join("" if l.lstrip().startswith("%") else re.sub(r"(?<!\\)%.*", "", l) for l in s.split("\n"))
    ob, cb = body.count("{"), body.count("}"); refs = set(re.findall(r"\\[cC]ref\{([^}]+)\}", body)); missing = {r.strip() for x in refs for r in x.split(",") if r.strip() not in labels}
    par = body.replace("\\$", "").count("$") % 2
    line = f"{f:48s} braces {ob}/{cb} {'OK' if ob==cb else 'MISMATCH'}; $ parity {'OK' if par==0 else 'ODD'}; missing labels {missing or '-'}"
    if ob != cb or par or missing: ok = False
    if f.startswith("data/"):
        m = re.search(r"\\begin\{tabular\}\{(.*)\}", s); spec = re.sub(r"@\{[^}]*\}", "", m.group(1)); spec = re.sub(r"p\{[^}]*\}", "p", spec); spec = re.sub(r">\{[^}]*\}", "", spec); ncol = len(re.sub(r"[^lrcp]", "", spec))
        rows = [l for l in s.split("\n") if l.strip().endswith("\\\\") and "cmidrule" not in l]
        counts = set()
        for l in rows:
            n = l.count("&") + 1 + sum(int(x) - 1 for x in re.findall(r"\\multicolumn\{(\d+)\}", l)); counts.add(n)
        line += f"; tabular {ncol} cols, rows have {sorted(counts)} cells ({len(rows)} rows)"
        if counts != {ncol}: ok = False
    print(line)
print("ALL OK" if ok else "PROBLEMS"); sys.exit(0 if ok else 1)
