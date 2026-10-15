"""Regenerate the manuscript's generated files in place, from the data archive and this checkout's scripts."""
from pathlib import Path
import shutil, subprocess, sys, tempfile, time
from .cached import _env, commands
from .runner import ASSETS, analysis_root

# In dependency order: the Starsim step also refits the combined score and the rank tables from all three worlds.
STEPS = ['micropolis', 'freeciv', 'starsim']
INPUTS = 'datasets/paper-inputs'
FREECIV = 'datasets/freeciv-source/worlds/freeciv/fbsim_v3'
FREECIV_RUN = 'run2_paper'

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

def install(src, paper, names):
    """A step that copies files a script wrote to `src` into the manuscript, at the given paths."""
    def copy():
        for name, dest in names: shutil.copyfile(src/name, paper/dest/name)
    copy.__name__ = 'install ' + ', '.join(name for name, _ in names)
    return copy

def _commands(step, data, paper, tmp):
    """(env, commands) for a step; a command is an argv list or a callable."""
    py = sys.executable
    if step == 'micropolis':
        return commands(step, data, paper, tmp, data/INPUTS/'micropolis')
    if step == 'freeciv':
        src = data/FREECIV; results = src/'results'; A = ASSETS/'freeciv'
        env = _env(tmp); env.update(FBSIM_SOURCE_ROOT=str(src), FBSIM_RUN=FREECIV_RUN, FBSIM_PAPER_ROOT=str(paper))
        return env, [[py, str(A/s), '--paper-root', str(paper)] for s in ['deliver_backing.py', 'make_freeciv_tables.py', 'make_freeciv_difficulty_table.py', 'make_freeciv_family_table.py']] + [
            [py, str(A/'make_freeciv_forecast_files.py'), '--results', str(results/FREECIV_RUN), '--sets', str(src/'sets/draw_v1'), '--out', str(paper/'data/freeciv')],
            [py, str(A/'effort_check_report.py'), str(results/FREECIV_RUN), str(results/'run2_effort'), str(results/'run2b_2026-09-20/batched'),
             '--run1', str(results/'run1_2026-09-09'), '--out', str(paper/'data/freeciv/freeciv_effort_check.json'), '--tex', str(paper/'data/appendix_tables/freeciv_effort.tex')],
            [py, str(A/'update_shared_tables.py'), '--paper-root', str(paper), '--final'],
            [py, str(A/'make_freeciv_figs.py'), '--paper-root', str(paper)]]
    analysis = analysis_root(data, tmp/'analysis'); S = ASSETS/'starsim'
    return _env(tmp), [
        [py, str(S/'integrate_fixed_state.py'), '--paper-root', str(paper), '--analysis-root', str(analysis),
         '--audit-root', str(data/'datasets/starsim-audit/production_v1'), '--out', str(tmp/'generated')],
        [py, str(S/'build_metadata.py'), '--paper-root', str(paper), '--csv', str(paper/'data/starsim/starsim_excess_long.csv'), '--out', str(tmp/'metadata')],
        install(tmp/'metadata', paper, [('roster_table.tex', 'data'), ('hosting_cost_table.tex', 'data'), ('cost_per_item.tex', 'data/appendix_tables')])]

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
