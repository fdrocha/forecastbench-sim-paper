"""Regenerate the manuscript's generated files in place, from the data archive and this checkout's scripts."""
from pathlib import Path
import shutil, subprocess, sys, tempfile, time
from .cached import _env, commands
from .runner import ASSETS, analysis_root

# In dependency order: the combined step refits the combined score and writes the cross-world tables from the
# other three steps' files.
STEPS = ['micropolis', 'freeciv', 'starsim', 'combined']
INPUTS = 'datasets/paper-inputs'
FREECIV = 'datasets/freeciv-source/worlds/freeciv/fbsim_v3'
FREECIV_RUN = 'run2_paper'
FREECIV_CANDIDATES = 'datasets/freeciv-candidates-20261022'
FREECIV_FRACTIONS = 'datasets/freeciv-source-deliveries/freeciv-v3-daca5a15-v1/sets/draw_v1/selection_fractions_bank_tails_mirrors.json'

def stage(inputs, paper):
    """Copy each file of paper-inputs to the same path under the manuscript's data/, if its content differs."""
    changed = []
    for p in sorted(inputs.rglob('*')):
        if not p.is_file(): continue
        dst = paper/'data'/p.relative_to(inputs)
        if dst.is_file() and dst.read_bytes() == p.read_bytes(): continue
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, dst); changed.append(dst)
    return changed

def uncommitted(paper):
    """Uncommitted changes under the manuscript's data/ and figures/, as git status lines; empty outside git."""
    if not (paper/'.git').exists(): return []
    out = subprocess.run(['git', '-C', str(paper), 'status', '--porcelain', '--', 'data', 'figures'], capture_output=True, text=True, check=True)
    return out.stdout.splitlines()

def _commands(step, data, paper, tmp):
    """(env, commands) for a step; a command is an argv list or a callable."""
    py = sys.executable
    if step == 'micropolis':
        # The baselines first, beside the inputs: analyze_paper.py draws them and delivers the JSON with the data.
        env, cmds = commands(step, data, paper, tmp, data/INPUTS/'micropolis')
        return env, [[py, str(ASSETS/'micropolis/scripts/micropolis_baselines.py'), '--datadir', str(tmp/'inputs'),
                      '--out', str(tmp/'inputs'/'micropolis_baselines.json')]] + cmds
    if step == 'freeciv':
        src = data/FREECIV; results = src/'results'; A = ASSETS/'freeciv'
        env = _env(tmp); env.update(FBSIM_SOURCE_ROOT=str(src), FBSIM_RUN=FREECIV_RUN, FBSIM_PAPER_ROOT=str(paper))
        # The baselines first: the per-model table and the capability figure draw them. They pool the generator's
        # candidates, which are private; without them the build keeps the archived JSON that stage() delivered.
        baselines = []
        if (data/FREECIV_CANDIDATES).is_dir():
            archived = data/INPUTS/'freeciv/freeciv_baselines.json'
            def deliver_freeciv_baselines():
                shutil.copyfile(archived, paper/'data/freeciv/freeciv_baselines.json')
            baselines = [[py, str(A/'make_freeciv_baselines.py'), '--sets', str(src/'sets/draw_v1'), '--reports', str(src/'reports'),
                          '--candidates', str(data/FREECIV_CANDIDATES), '--scores', str(results/FREECIV_RUN/'scores_v1/score_items.csv.gz'),
                          '--out', str(archived)], deliver_freeciv_baselines]
        return env, baselines + [
            [py, str(A/s), '--paper-root', str(paper)] for s in ['deliver_backing.py', 'make_freeciv_tables.py', 'make_freeciv_difficulty_table.py', 'make_freeciv_family_table.py']] + [
            [py, str(A/'make_freeciv_forecast_files.py'), '--results', str(results/FREECIV_RUN), '--sets', str(src/'sets/draw_v1'), '--out', str(paper/'data/freeciv')],
            [py, str(A/'make_freeciv_grouping.py'), '--one', str(results/'run1_2026-09-09'), '--grouped', str(results/FREECIV_RUN),
             '--shuffled', str(results/'run2_shuffled'), '--paper-root', str(paper)],
            [py, str(A/'effort_check_report.py'), str(results/FREECIV_RUN), str(results/'run2_effort'), str(results/'run2b_2026-09-20/batched'),
             '--run1', str(results/'run1_2026-09-09'), '--out', str(paper/'data/freeciv/freeciv_effort_check.json')],
            [py, str(A/'validation_stats.py'), '--paper-root', str(paper)],
            [py, str(A/'make_freeciv_figs.py'), '--paper-root', str(paper)],
            [py, str(A/'selection_weights.py'), '--sets', str(src/'sets/draw_v1'), '--fractions', str(data/FREECIV_FRACTIONS),
             '--out', str(paper/'data/freeciv/freeciv_selection_weights.csv')],
            [py, str(A/'make_freeciv_macros.py'), '--paper-root', str(paper)]]
    if step == 'starsim':
        analysis = analysis_root(data, tmp/'analysis')
        # The baselines first, from the audit's outputs: integrate_fixed_state.py draws them in its figure and table.
        audit = data/'datasets/starsim-audit/production_v1'
        return _env(tmp), [[py, str(ASSETS/'starsim'/'starsim_baselines.py'), '--audit-root', str(audit), '--analysis-root', str(analysis),
                            '--out', str(paper/'data/starsim/starsim_baselines.json')],
                           [py, str(ASSETS/'starsim'/'integrate_fixed_state.py'), '--paper-root', str(paper), '--analysis-root', str(analysis),
                            '--audit-root', str(audit), '--out', str(tmp/'generated')]]
    C = ASSETS/'combined'
    return _env(tmp), [[py, str(C/'refit_combined.py'), '--paper-root', str(paper), '--out', str(tmp/'generated')],
                       [py, str(C/'make_roster_table.py'), '--paper-root', str(paper)],
                       [py, str(C/'make_validation_tables.py'), '--paper-root', str(paper)],
                       [py, str(C/'make_baseline_table.py'), '--paper-root', str(paper)]]

def run(steps, data, paper, allow_dirty=False):
    unknown = set(steps) - set(STEPS)
    if unknown: raise ValueError(f'Unknown step {", ".join(sorted(unknown))}; choose from {", ".join(STEPS)}')
    steps = [s for s in STEPS if s in steps] if steps else STEPS
    if not (paper/'main.tex').is_file(): raise ValueError(f'{paper} is not the manuscript checkout: no main.tex')
    inputs = data/INPUTS
    if not inputs.is_dir(): raise ValueError(f'Missing {inputs}; FBSIM_DATA_ROOT must be the data archive\'s data/ folder')
    dirty = uncommitted(paper)
    if dirty and not allow_dirty:
        raise ValueError('The manuscript has uncommitted changes under data/ or figures/, which build would overwrite:\n  '
                         + '\n  '.join(dirty) + '\nCommit or discard them, or pass --allow-dirty.')
    start = time.monotonic()
    print(f'paper:  {paper}\ninputs: {inputs}\nsteps:  {", ".join(steps)}')
    for p in stage(inputs, paper): print(f'Staged {p.relative_to(paper)}')
    with tempfile.TemporaryDirectory(prefix='fbsim-build-') as t:
        for step in steps:
            tmp = Path(t)/step; tmp.mkdir()
            env, cmds = _commands(step, data, paper, tmp)
            env.setdefault('SOURCE_DATE_EPOCH', '0')  # fixed PDF dates, so an unchanged figure leaves no diff
            for cmd in cmds:
                print(f'\n== {step}: {cmd.__name__ if callable(cmd) else Path(cmd[1]).name}', flush=True)
                cmd() if callable(cmd) else subprocess.run(cmd, env=env, check=True)
    print(f'\nBuilt {", ".join(steps)} in {time.monotonic()-start:.0f}s')
    if (paper/'.git').exists():
        subprocess.run(['git', '-C', str(paper), 'status', '--short', '--', 'data', 'figures'])
