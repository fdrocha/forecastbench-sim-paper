"""Private worker for fbsim-paper case-study, launched with the offline guard."""
from pathlib import Path
import json
import socket
import sys
from . import diagnostics, robustness, context, figures, parser_audit


def main():
    # Check the guard before reading inputs; refuse a direct unguarded invocation.
    try:
        socket.create_connection(('127.0.0.1', 9))
    except Exception as error:
        if 'offline reproduction guard' not in str(error):
            raise RuntimeError('Launch through fbsim-paper case-study with the offline guard') from error
    else:
        raise RuntimeError('Offline guard is not active')
    config = json.loads(Path(sys.argv[1]).read_text())
    fc, ts, out = (Path(config[k]) for k in ['freeciv_root', 'measles_root', 'output'])
    scores = json.loads(Path(config['measles_roster']).read_text())
    diagnostics.run(fc, ts, scores, out)
    context.run(ts, out)
    robustness.run(out)
    if config['raw_repo']:
        parser_audit.run(out, ts, fc, Path(config['raw_repo']), config['raw_ref'])
    figures.run(out)
    (out/'run-status.json').write_text(json.dumps(dict(status='PASS', network_guard='PASS',
        parser_audit='PASS' if config['raw_repo'] else 'NOT_RUN', simulations=0, model_calls=0), indent=2)+'\n')


if __name__ == '__main__':
    main()
