"""Compare two paper folders' data/ and figures/: JSON by value, PDFs without metadata, the rest byte for byte."""
from pathlib import Path
import json, math, re, subprocess
from PIL import Image

TOL = 1e-12
PDF_META = re.compile(rb'/(CreationDate|ModDate|Producer|Creator) *\([^)]*\)|/ID *\[[^\]]*\]')


def _same_json(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        keys = (a.keys() | b.keys()) - {'generated'}
        return all(k in a and k in b and _same_json(a[k], b[k]) for k in keys)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same_json(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return a == b or math.isclose(a, b, rel_tol=TOL, abs_tol=TOL)
    return a == b


def _status(a, b):
    """'same', 'same-value' (JSON within tolerance), 'same-content' (PDF metadata only) or 'differs'."""
    x, y = a.read_bytes(), b.read_bytes()
    if x == y: return 'same'
    if a.suffix == '.json':
        try: return 'same-value' if _same_json(json.loads(x), json.loads(y)) else 'differs'
        except ValueError: return 'differs'
    if a.suffix == '.pdf' and PDF_META.sub(b'', x) == PDF_META.sub(b'', y): return 'same-content'
    return 'differs'


def _figure_status(a, b):
    """Check that changed images are readable before reporting them for review."""
    if a.suffix == '.png':
        try:
            with Image.open(a) as x, Image.open(b) as y:
                if x.size == y.size and x.convert('RGBA').tobytes() == y.convert('RGBA').tobytes():
                    return 'same-pixels'
                y.load()
        except OSError:
            return 'invalid-figure'
    else:
        # Parse every page with the same Poppler dependency as cached reproduction.
        result = subprocess.run(['pdftotext', str(b), '-'], capture_output=True)
        if result.returncode or b'Syntax Error' in result.stderr:
            return 'invalid-figure'
    return 'review-figure'


def run(expected, rebuilt, strict_figures=False):
    expected, rebuilt = Path(expected), Path(rebuilt)
    files = lambda root: {p.relative_to(root).as_posix() for sub in ['data', 'figures'] for p in (root/sub).rglob('*')
                          if p.is_file() and p.name != '.DS_Store'}
    e, r = files(expected), files(rebuilt)
    if not e: raise ValueError(f'No data/ or figures/ files under {expected}')
    counts, problems, figure_review = {}, [], []
    for rel in sorted(e | r):
        s = 'missing' if rel not in r else 'extra' if rel not in e else _status(expected/rel, rebuilt/rel)
        if s == 'differs' and rel.startswith('figures/') and Path(rel).suffix in {'.pdf', '.png'}:
            s = _figure_status(expected/rel, rebuilt/rel)
            if s == 'review-figure':
                figure_review.append(rel)
        counts[s] = counts.get(s, 0) + 1
        if s in ('differs', 'missing', 'extra', 'invalid-figure', 'same-content') or (strict_figures and s in ('review-figure', 'same-pixels')): problems.append((s, rel))
    differences = [f'{s}: {rel}' for s, rel in problems if s != 'same-content']
    return dict(status='PASS' if not differences else 'FAIL', figure_review=figure_review, files=len(e | r), counts=counts, differences=differences,
                pdf_metadata_only=[rel for s, rel in problems if s == 'same-content'])
