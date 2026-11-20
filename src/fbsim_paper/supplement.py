"""Build the anonymized reviewer supplement: the archive inputs of `build` and a snapshot of its outputs."""
from pathlib import Path
import csv, fnmatch, gzip, hashlib, io, json, re, shutil, subprocess, tarfile, zipfile
from .build import uncommitted

ASSETS = Path(__file__).parent/'assets'/'supplement'
NAME = 'fbsim-supplementary'
FC = 'freeciv-source/worlds/freeciv/fbsim_v3'
MP = 'micropolis-source-deliveries/micropolis-data-20260924-v1/extracted/micropolis'

# Files under the archive's datasets/ that `build` (all steps, incl. case-study) reads, as globs; `**` spans folders.
INPUTS = [
    'paper-inputs/**',
    f'{FC}/sets/draw_v1/*', f'{FC}/reports/**', f'{FC}/run/models_v2.csv', f'{FC}/results/run2_paper/**',
    f'{FC}/results/run1_2026-09-09/scores_v1/score_items.csv.gz', f'{FC}/results/run1_2026-09-09/elicit_medium/*/results.jsonl',
    f'{FC}/results/run2_effort/*/results.jsonl', f'{FC}/results/run2_effort/*/items.json',
    f'{FC}/results/run2_shuffled/scores_v1/score_items.csv.gz', f'{FC}/results/run2b_2026-09-20/batched/*/results.jsonl',
    'freeciv-candidates/*', 'freeciv-source-deliveries/freeciv-v3-daca5a15-v1/**',
    'analysis-original/results/causal/rerun_lowest/**', 'analysis-original/results/causal/data/worlds/**',
    'analysis-original/results/causal/starsim_causal/worlds.json', 'analysis-original/results/causal/starsim_causal/worlds_hold.json',
    'analysis-original/results/causal/starsim_causal/models.csv',
    'starsim-audit/production_v1/rescore/**',
    'measles-case-study/**',
]
# Items Appendix F describes that `build` does not read; the Micropolis results are packed into one .tar.xz.
EXTRAS = ['freeciv-source-deliveries/natcond-replays-20260923-v1/*']
PACKED = {f'{MP}/results.tar.xz': [f'{MP}/{d}/**' for d in ['runs', 'ground_truth', 'binary', 'continuous', 'knowledge_eval']]}
# Model replies are left out: the Micropolis reply caches and the measles replies.
EXCLUDE = ['*/.DS_Store', '*/cache/*', 'measles-case-study/timeseries/data/forecasts/*']
# Supplement files replaced by reviewer-facing versions.
OVERRIDES = {'measles-case-study/README.md': ASSETS/'measles-README.md'}
TEXT = ('.json', '.jsonl', '.csv', '.md', '.txt', '.tex', '.sh', '.log', '.py', '.yaml', '.toml', '.html', '.bib')


def _select(root, patterns):
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())
    return [f for f in files if any(fnmatch.fnmatch(f, g.replace('**', '*')) for g in patterns)
            and not any(fnmatch.fnmatch(f, x) for x in EXCLUDE)]


class Anonymizer:
    """Applies exact-text replacements and checks the blocklist, from the anonymization folder `anon`."""
    def __init__(self, anon):
        anon = Path(anon)
        if not (anon/'replacements.csv').is_file() or not (anon/'blocklist.txt').is_file():
            raise ValueError(f'{anon} lacks replacements.csv or blocklist.txt; pass --anonymization')
        with open(anon/'replacements.csv', newline='') as f:
            self.rows = [(r['original'], r['replacement']) for r in csv.DictReader(f)]
        lines = (anon/'blocklist.txt').read_text().splitlines()
        self.block = re.compile('|'.join(f'(?:{l})' for l in lines if l.strip() and not l.startswith('#')), re.I)
        self.edited = {}

    def text(self, rel, data):
        """Replace in text bytes; record the count of replacements by path."""
        s = data.decode('utf-8')
        n = 0
        for a, b in self.rows:
            n += s.count(a); s = s.replace(a, b)
        if n: self.edited[rel] = self.edited.get(rel, 0) + n
        return s.encode('utf-8') if n else data

    def file(self, rel, data):
        """Anonymize a file's bytes: text, or text inside .gz; other binaries pass through for the scan."""
        if rel.endswith(TEXT): return self.text(rel, data)
        if rel.endswith('.gz') and not rel.endswith('.tar.gz'):
            raw = gzip.decompress(data); new = self.text(rel, raw)
            return data if new is raw else gzip.compress(new, mtime=0)
        return data

    def leaks(self, rel, data):
        """Blocklist hits in a file (text, .gz, tar/zip members; printable runs of other binaries)."""
        if rel.endswith(('.tar.gz', '.tar.xz')):
            with tarfile.open(fileobj=io.BytesIO(data)) as t:
                return [h for m in t.getmembers() if m.isfile() for h in self.leaks(f'{rel}!{m.name}', t.extractfile(m).read())]
        if rel.endswith('.npz'):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return [h for n in z.namelist() for h in self.leaks(f'{rel}!{n}', z.read(n))]
        if rel.endswith('.gz'): return self.leaks(rel[:-3], gzip.decompress(data))
        if rel.endswith(TEXT): text = data.decode('utf-8', 'replace')
        else: text = '\n'.join(m.decode('ascii') for m in re.findall(rb'[ -~]{8,}', data))
        return [(rel, m.group(0)) for m in self.block.finditer(text)]


def _commit(paper):
    return subprocess.run(['git', '-C', str(paper), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()


def run(data, paper, anonymization, out=None, allow_dirty=False, max_mb=95):
    data, paper = Path(data), Path(paper)
    if not (paper/'main.tex').is_file(): raise ValueError(f'{paper} is not the manuscript checkout: no main.tex')
    if not (paper/'.git').exists(): raise ValueError(f'{paper} is not a Git checkout; the supplement is named after its commit')
    dirty = uncommitted(paper)
    if dirty and not allow_dirty:
        raise ValueError('The manuscript has uncommitted changes under data/ or figures/:\n  ' + '\n  '.join(dirty) + '\nCommit them or pass --allow-dirty.')
    commit = _commit(paper)
    out = Path(out) if out else data.resolve().parent.parent/f'{NAME}-{commit}'
    zpath = out.parent/f'{out.name}.zip'
    if out.exists() or zpath.exists(): raise ValueError(f'{out} or {zpath} exists; the supplement is never overwritten')
    if any((p/'.git').exists() for p in [out.parent, *out.parent.parents]): raise ValueError('Output must be outside Git checkouts')
    anon = Anonymizer(anonymization)
    ds = data/'datasets'
    top = out/NAME
    copied = []
    for rel in sorted(set(_select(ds, INPUTS + EXTRAS))):
        src = OVERRIDES.get(rel, ds/rel)
        dst = top/'data/datasets'/rel; dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(anon.file(f'data/datasets/{rel}', src.read_bytes())); copied.append(rel)
    for packed, patterns in PACKED.items():
        dst = top/'data/datasets'/packed; dst.parent.mkdir(parents=True, exist_ok=True)
        base = Path(packed).parent
        with tarfile.open(dst, 'w:xz') as t:
            for rel in _select(ds, patterns):
                b = anon.file(f'data/datasets/{packed}!{rel}', (ds/rel).read_bytes())
                info = tarfile.TarInfo(Path(rel).relative_to(base).as_posix()); info.size = len(b); info.mode = 0o644
                t.addfile(info, io.BytesIO(b))
    # The paper snapshot: the manuscript's data/ and figures/, without its LaTeX source.
    for sub in ['data', 'figures']:
        for p in sorted((paper/sub).rglob('*')):
            if p.is_file() and p.name != '.DS_Store':
                rel = p.relative_to(paper).as_posix(); dst = top/'paper'/rel; dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(anon.file(f'paper/{rel}', p.read_bytes()))
    shutil.copyfile(ASSETS/'main.tex', top/'paper/main.tex')
    for name in ['README.md', 'LICENSE.md']:
        (top/name).write_text((ASSETS/name).read_text().replace('{commit}', commit))
    leaks = [h for p in sorted(top.rglob('*')) if p.is_file() for h in anon.leaks(p.relative_to(top).as_posix(), p.read_bytes())]
    if leaks:
        raise ValueError('Blocklisted strings remain (output left for inspection):\n  ' + '\n  '.join(f'{f}: {s!r}' for f, s in leaks[:50]))
    with open(top/'ANONYMIZED_FILES.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['path', 'replacements']); w.writerows(sorted(anon.edited.items()))
    files = sorted(p for p in top.rglob('*') if p.is_file())
    (top/'SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(top).as_posix()}\n' for p in files))
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(top.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(out).as_posix())
    mb = zpath.stat().st_size/1e6
    result = dict(status='PASS', manuscript_commit=commit, folder=str(top), zip=str(zpath), zip_mb=round(mb, 1),
                  files=len(files) + 1, anonymized_files=len(anon.edited), archive_inputs=len(copied))
    if mb > max_mb: result['status'] = f'FAIL: zip is {mb:.1f} MB, over {max_mb} MB'
    return result
