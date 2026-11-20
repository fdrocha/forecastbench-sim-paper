"""Check the data folder against its SHA256SUMS.txt, and the installed scorers against the benchmark pin."""
import hashlib, json
from pathlib import Path

SUMS = 'SHA256SUMS.txt'   # at the top of the data folder; covers every file except itself
PIN = Path(__file__).parent/'assets'/'benchmark-pin.json'
SKIP = {'.DS_Store', SUMS}


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def _files(data):
    return sorted(p.relative_to(data).as_posix() for p in data.rglob('*') if p.is_file() and p.name not in SKIP)


def write(data):
    """Write data/SHA256SUMS.txt for every file in the data folder; return the number of files."""
    files = _files(data)
    (data/SUMS).write_text(''.join(f'{sha(data/rel)}  {rel}\n' for rel in files))
    return len(files)


def check(data):
    """{files, missing, changed, added} relative to data/SHA256SUMS.txt."""
    if not (data/SUMS).is_file():
        raise ValueError(f'Missing {data/SUMS}; --data-root must be the data folder (write it with --write)')
    listed = dict(reversed(line.rstrip('\n').split('  ', 1)) for line in open(data/SUMS) if '  ' in line)
    missing = [rel for rel in sorted(listed) if not (data/rel).is_file()]
    changed = [rel for rel in sorted(listed) if (data/rel).is_file() and sha(data/rel) != listed[rel]]
    added = [rel for rel in _files(data) if rel not in listed]
    return dict(files=len(listed), missing=missing, changed=changed, added=added)


def pin():
    """Scoring files of the installed fbsim-benchmark whose hash differs from the pin (empty when they match)."""
    from fbsim_benchmark.scoring import pandemic
    scoring = Path(pandemic.__file__).parent
    pinned = json.loads(PIN.read_text())['scoring_hashes']
    return sorted(name for name, h in pinned.items() if not (scoring/name).is_file() or sha(scoring/name) != h)
