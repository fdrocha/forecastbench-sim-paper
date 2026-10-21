"""Resolve the analysis checkout explicitly; never write into cached input runs."""
import argparse
import sys
from pathlib import Path


def analysis_modules():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--analysis-root', type=Path, default=Path.cwd())
    args, _ = parser.parse_known_args()
    root = args.analysis_root.resolve()
    table = root / 'results' / 'table'
    if not (table / 'build_table.py').is_file():
        raise SystemExit('Run from the iclr-2026 root or pass --analysis-root PATH.')
    # The documented sibling checkout supplies fbsim_core; installed packages also work.
    core = root.parent / 'forecastbench-sim' / 'packages' / 'fbsim-core'
    if core.is_dir():
        sys.path.insert(0, str(core))
    sys.path.insert(0, str(table))
    import build_table
    import figures
    return root, build_table, figures


def use_cached_runs(bt, runs):
    """Equivalent source selection to build_table.use_runs, without creating its output dir."""
    for name, rel in bt.RERUN_FILES.items():
        qtype, cond, rung, _, worlds, truth, template = bt.SOURCES[name]
        path = Path(runs).resolve() / rel
        if not path.is_file():
            raise SystemExit(f'Missing cached input: {path}')
        bt.SOURCES[name] = (qtype, cond, rung, path, worlds, truth, template)
