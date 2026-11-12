"""Correlations of the combined score and ECI with FutureEval, Prophet Arena and ForecastBench (Appendix C).
    python external_benchmarks.py --paper-root PAPER

Reads data/micropolis/model_scores.csv and data/combined_score.json. Writes data/external_benchmarks.json,
data/external_benchmarks_table.tex and data/external_benchmarks_macros.tex. Spearman with ties kept; partials as in
partial_correlations.py; 95% percentile bootstrap over models, 10,000 resamples, seed 2026, the same resamples for
every column of a panel; n_boot_valid counts the finite draws. Prophet Arena Brier is sign-flipped so that
positive means agreement.
"""
import argparse, csv, json
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
from paper_roster import paper_roster
from partial_correlations import partial_spearman

RESAMPLES, SEED = 10000, 2026
BENCH = {'FE': ('FutureEval', 'FutureEval', 1), 'PA': ('Prophet Arena', 'PABrier', -1),
         'FB': ('ForecastBench', 'FBOverall', 1)}
STATS = ['theta', 'eci', 'theta_given_eci', 'eci_given_theta']


def stats(y, theta, eci):
    """Spearman of the benchmark with theta and ECI, and each given the other."""
    rho = lambda a, b: float(spearmanr(a, b).statistic)
    return dict(theta=rho(y, theta), eci=rho(y, eci), theta_given_eci=partial_spearman(y, theta, eci),
                eci_given_theta=partial_spearman(y, eci, theta))


def panel(rows, theta, eci):
    """Point and interval of every statistic for each benchmark in rows, plus the first-minus-second difference
    when there are two, all on the same model resamples."""
    n = len(theta)
    idx = np.random.default_rng(SEED).integers(0, n, (RESAMPLES, n))
    out, draws = {}, {}
    for key, y in rows.items():
        point = stats(y, theta, eci)
        with np.errstate(all='ignore'):
            d = [stats(y[i], theta[i], eci[i]) for i in idx]
        draws[key] = {s: np.array([x[s] for x in d]) for s in STATS}
        out[key] = {s: dict(rho=point[s], ci=list(map(float, np.nanquantile(draws[key][s], [.025, .975]))),
                            n_boot_valid=int(np.isfinite(draws[key][s]).sum())) for s in STATS}
        out[key]['n'] = n
    if len(rows) == 2:
        a, b = rows
        out['difference'] = {s: dict(rho=out[a][s]['rho'] - out[b][s]['rho'],
                                     ci=list(map(float, np.nanquantile(draws[a][s] - draws[b][s], [.025, .975]))),
                                     n_boot_valid=int(np.isfinite(draws[a][s] - draws[b][s]).sum()))
                             for s in STATS}
        out['difference']['n'] = n
    return out


def cell(r, signed=False):
    f = (lambda v: f'{v:+.2f}') if signed else (lambda v: f'{v:.2f}')
    return f'${f(r["rho"])}$ {{\\scriptsize$[{f(r["ci"][0])},{f(r["ci"][1])}]$}}'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--paper-root', type=Path, required=True)
    P = ap.parse_args().paper_root.resolve()
    MODELS, ECI, SHORT = paper_roster(P)
    theta_all = json.loads((P / 'data/combined_score.json').read_text())['theta']
    score = {k: {} for k in BENCH}
    for r in csv.DictReader(open(P / 'data/micropolis/model_scores.csv')):
        m = SHORT.get(r['slug'])
        if m not in MODELS:
            continue
        for k, (_, col, sign) in BENCH.items():
            if r[col]:
                score[k][m] = sign * float(r[col])

    def arrays(ms, keys):
        return ({k: np.array([score[k][m] for m in ms]) for k in keys},
                np.array([theta_all[m] for m in ms]), np.array([ECI[m] for m in ms]))

    result = dict(script='forecastbench-sim-paper/src/fbsim_paper/assets/combined/external_benchmarks.py',
                  coverage={k: [m for m in MODELS if m in score[k]] for k in BENCH}, own={}, between={})
    for k in BENCH:
        result['own'][k] = panel(*arrays(result['coverage'][k], [k]))[k]
    matched = [m for m in MODELS if m in score['FE'] and m in score['FB']]
    result['matched'] = panel(*arrays(matched, ['FE', 'FB']))
    result['matched_models'] = matched
    for a, b in [('FB', 'FE'), ('FB', 'PA'), ('FE', 'PA')]:
        ms = [m for m in MODELS if m in score[a] and m in score[b]]
        result['between'][f'{a}-{b}'] = dict(n=len(ms), rho=float(spearmanr([score[a][m] for m in ms],
                                                                            [score[b][m] for m in ms]).statistic))
    (P / 'data/external_benchmarks.json').write_text(json.dumps(result, indent=1) + '\n')

    head = (r'Benchmark & $n$ & $\theta_m$ & ECI & $\theta_m$ given ECI & ECI given $\theta_m$ \\')
    lines = [r'\begin{tabular}{lrcccc}', r'\toprule', head, r'\midrule',
             r'\multicolumn{6}{@{}l}{\emph{(a) Models each benchmark covers}} \\']
    row = lambda name, r, signed=False: (f'{name} & {r["n"]} & ' + ' & '.join(cell(r[s], signed) for s in STATS) + r' \\')
    for k in BENCH:
        lines.append(row(BENCH[k][0], result['own'][k]))
    lines += [r'\midrule', rf'\multicolumn{{6}}{{@{{}}l}}{{\emph{{(b) The {len(matched)} models both FutureEval and '
                           r'ForecastBench cover}} \\',
              row('FutureEval', result['matched']['FE']), row('ForecastBench', result['matched']['FB']),
              row('Difference', result['matched']['difference'], signed=True).replace(f' & {len(matched)} & ', ' & & '),
              r'\bottomrule', r'\end{tabular}']
    (P / 'data/external_benchmarks_table.tex').write_text('\n'.join(lines) + '\n')

    tag = {'theta': 'Theta', 'eci': 'Eci', 'theta_given_eci': 'ThetaGivenEci', 'eci_given_theta': 'EciGivenTheta'}
    macros = []
    def put(key, r):
        macros.append(f'\\newcommand{{\\{key}}}{{{r["rho"]:.2f}}}')
        macros.append(f'\\newcommand{{\\{key}CI}}{{[{r["ci"][0]:.2f}, {r["ci"][1]:.2f}]}}')
    for k in BENCH:
        macros.append(f'\\newcommand{{\\Ext{k}N}}{{{result["own"][k]["n"]}}}')
        for s in STATS:
            put(f'Ext{k}{tag[s]}', result['own'][k][s])
    macros.append(f'\\newcommand{{\\ExtMatchedN}}{{{len(matched)}}}')
    for k in ['FE', 'FB', 'difference']:
        for s in STATS:
            put(f'ExtMatched{"Diff" if k == "difference" else k}{tag[s]}', result['matched'][k][s])
    for pair, r in result['between'].items():
        macros.append(f'\\newcommand{{\\ExtBetween{pair.replace("-", "")}}}{{{r["rho"]:.2f}}}')
    (P / 'data/external_benchmarks_macros.tex').write_text(
        '% Generated by forecastbench-sim-paper src/fbsim_paper/assets/combined/external_benchmarks.py\n'
        + '\n'.join(macros) + '\n')
    for k in BENCH:
        print(BENCH[k][0], {s: round(result['own'][k][s]['rho'], 2) for s in STATS})
    print('matched', len(matched), {k: {s: round(result['matched'][k][s]['rho'], 2) for s in STATS}
                                    for k in ['FE', 'FB', 'difference']})
    print('between', result['between'])
