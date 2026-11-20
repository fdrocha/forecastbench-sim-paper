"""ForecastBench-Sim paper analysis: build the manuscript's generated files from the data folder, and check them."""
from pathlib import Path
import argparse, json, os, subprocess, sys


def load_env():
    """Fill unset variables from .env in this checkout, else the current directory; shell and flags win."""
    from dotenv import load_dotenv
    for d in (Path(__file__).resolve().parents[2], Path.cwd()):
        if (d/'.env').is_file(): load_dotenv(d/'.env', override=False); return


def main():
    load_env()
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest='command', required=True)
    s.add_parser('smoke', help='Check imports and synthetic scoring; no data needed')
    data_help = 'The data folder (the one holding datasets/ and SHA256SUMS.txt); default FBSIM_DATA_ROOT'
    q = s.add_parser('check-data', help='Check the data folder against its SHA256SUMS.txt and the scorers against the pin')
    q.add_argument('--data-root', type=Path, default=os.environ.get('FBSIM_DATA_ROOT'), help=data_help)
    q.add_argument('--write', action='store_true', help='Rewrite SHA256SUMS.txt from the current files instead')
    q = s.add_parser('build', help='Regenerate the manuscript checkout\'s generated files in place')
    q.add_argument('steps', nargs='*', help='Any of micropolis, freeciv, starsim, combined, case-study (default: all, in that order)')
    q.add_argument('--data-root', type=Path, default=os.environ.get('FBSIM_DATA_ROOT'), help=data_help)
    q.add_argument('--paper-root', type=Path, default=os.environ.get('FBSIM_PAPER_ROOT'))
    q.add_argument('--allow-dirty', action='store_true', help='Run even if the manuscript has uncommitted changes under data/ or figures/')
    q.add_argument('--include-micropolis-conditionals', action='store_true', help='Opt into the additional Micropolis studies and eleven-cell score; default preserves the nine-cell ICLR R&R')
    q = s.add_parser('case-study', help='Offline FreeCiv/measles calibration in a new output directory')
    q.add_argument('--data-root', type=Path, default=os.environ.get('FBSIM_DATA_ROOT'), help='Data folder; supplies any input path not given')
    q.add_argument('--freeciv-root', type=Path)
    q.add_argument('--measles-root', type=Path, help='Historical timeseries folder containing data/')
    q.add_argument('--measles-roster', type=Path, help='JSON mapping model IDs to ECI scores')
    q.add_argument('--output', type=Path, required=True)
    q.add_argument('--parser-audit', action='store_true', help='Also re-parse the raw FreeCiv and measles replies')
    q = s.add_parser('supplement', help='Write the anonymized reviewer supplement (folder and zip) next to the data archive')
    q.add_argument('--data-root', type=Path, default=os.environ.get('FBSIM_DATA_ROOT'), help=data_help)
    q.add_argument('--paper-root', type=Path, default=os.environ.get('FBSIM_PAPER_ROOT'))
    q.add_argument('--anonymization', type=Path, help='Folder with replacements.csv and blocklist.txt (default: private-data/datasets/supplement-anonymization beside the data folder)')
    q.add_argument('--out', type=Path, help='New output folder (default: fbsim-supplementary-<manuscript commit> beside the archive)')
    q.add_argument('--allow-dirty', action='store_true', help='Run even if the manuscript has uncommitted changes under data/ or figures/')
    q.add_argument('--max-mb', type=float, default=95, help='Fail if the zip is larger (default 95)')
    q = s.add_parser('compare', help='Compare a rebuilt paper folder with the expected one (data/ and figures/)')
    q.add_argument('--strict-figures', action='store_true', help='Also fail on image encoding or rendering differences (except PDF metadata)')
    q.add_argument('expected', type=Path); q.add_argument('rebuilt', type=Path)
    a = p.parse_args()

    if a.command == 'smoke':
        from fbsim_benchmark.scoring import pandemic
        assert pandemic.crps5([1, 1, 1, 1, 1], [1]) == 0
        print(json.dumps(dict(status='PASS', scope='import and synthetic scoring only; no paper inputs'))); return
    if a.command == 'compare':
        from .compare import run
        try: result = run(a.expected, a.rebuilt, a.strict_figures)
        except ValueError as e: p.error(str(e))
        print(json.dumps(result, indent=2))
        if result['status'] != 'PASS': sys.exit(f"{len(result['differences'])} files differ")
        return
    if a.command == 'case-study':
        from .case_study import run, archive_inputs
        paths = [a.freeciv_root, a.measles_root, a.measles_roster]
        if None in paths:
            if a.data_root is None: p.error('Pass --freeciv-root, --measles-root and --measles-roster, or --data-root DIR (or set FBSIM_DATA_ROOT).')
            paths = [x if x is not None else d for x, d in zip(paths, archive_inputs(Path(a.data_root).expanduser()))]
        try: result = run(*paths, a.output, a.parser_audit)
        except (ValueError, FileNotFoundError) as e: p.error(str(e))
        print(json.dumps(result, indent=2)); return

    if a.data_root is None: p.error('Pass --data-root DIR or set FBSIM_DATA_ROOT (in the shell or .env); no default path is assumed.')
    data = Path(a.data_root).expanduser().resolve()
    if a.command == 'check-data':
        from . import datacheck
        if a.write:
            print(json.dumps(dict(written=str(data/datacheck.SUMS), files=datacheck.write(data)), indent=2)); return
        try: result = datacheck.check(data)
        except ValueError as e: p.error(str(e))
        result['scorers_differing_from_pin'] = datacheck.pin()
        print(json.dumps(result, indent=2))
        problems = [f'{len(result[k])} {k}' for k in ('missing', 'changed', 'added', 'scorers_differing_from_pin') if result[k]]
        if problems: sys.exit(', '.join(problems))
        return
    if a.paper_root is None: p.error('Pass --paper-root DIR or set FBSIM_PAPER_ROOT (in the shell or .env).')
    paper = Path(a.paper_root).expanduser().resolve()
    if a.command == 'supplement':
        from .supplement import run
        anon = a.anonymization or data.parent/'private-data/datasets/supplement-anonymization'
        try: result = run(data, paper, anon, a.out, a.allow_dirty, a.max_mb)
        except ValueError as e: p.error(str(e))
        print(json.dumps(result, indent=2))
        if result['status'] != 'PASS': sys.exit(result['status'])
        return
    if a.command == 'build':
        from .build import run
        try: run(a.steps, data, paper, a.allow_dirty, a.include_micropolis_conditionals)
        except ValueError as e: p.error(str(e))
        except subprocess.CalledProcessError as e: sys.exit(f'build failed: {e.cmd[1]} exited with status {e.returncode}')
