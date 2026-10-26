"""Compare the working data archive with its v1 version: v1 files must be unchanged; list what was added since."""
import hashlib
from pathlib import Path

V1_SUMS = 'metadata/SHA256SUMS.txt'   # v1's hash of every archive member except itself

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()

def check(root):
    """{missing, changed, added} relative to v1, for the archive whose top folder (holding data/) is `root`."""
    v1 = dict(reversed(line.rstrip('\n').split('  ', 1)) for line in open(root/V1_SUMS) if '  ' in line)
    v1[V1_SUMS] = None
    missing, changed = [], []
    for rel, digest in sorted(v1.items()):
        p = root/rel
        if not p.is_file(): missing.append(rel)
        elif digest and sha(p) != digest: changed.append(rel)
    added = sorted(str(p.relative_to(root)) for p in root.rglob('*')
                   if p.is_file() and p.name != '.DS_Store' and str(p.relative_to(root)) not in v1)
    return dict(v1_files=len(v1), missing=missing, changed=changed, added=added)
