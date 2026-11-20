"""Synthetic checks of the reviewer supplement's comparison and anonymization; no private inputs."""
import gzip, json
import pytest
from fbsim_paper.compare import run as compare
from fbsim_paper.supplement import Anonymizer


def _paper(root, files):
    for rel, data in files.items():
        p = root/rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    return root


def test_compare_tolerates_dates_float_noise_and_pdf_metadata(tmp_path):
    pdf = b'%PDF-1.4\n<< /Producer (Matplotlib v3.10.3) /CreationDate (D:2026) >>\nstream'
    a = _paper(tmp_path/'a', {'data/x.json': b'{"generated": "2026-10-26", "v": 0.8818577226556832}',
                              'figures/f.pdf': pdf, 'data/t.tex': b'same'})
    b = _paper(tmp_path/'b', {'data/x.json': b'{"generated": "2026-11-16", "v": 0.8818577226556833}',
                              'figures/f.pdf': pdf.replace(b'3.10.3', b'3.10.8'), 'data/t.tex': b'same'})
    r = compare(a, b)
    assert r['status'] == 'PASS' and r['pdf_metadata_only'] == ['figures/f.pdf']


def test_compare_reports_real_differences(tmp_path):
    a = _paper(tmp_path/'a', {'data/x.json': b'{"v": 0.5}', 'data/t.tex': b'1', 'data/only.csv': b''})
    b = _paper(tmp_path/'b', {'data/x.json': b'{"v": 0.6}', 'data/t.tex': b'2'})
    assert compare(a, b)['differences'] == ['missing: data/only.csv', 'differs: data/t.tex', 'differs: data/x.json']


def test_anonymizer_replaces_text_and_gz_and_flags_leaks(tmp_path):
    d = tmp_path/'anonymization'; d.mkdir()
    (d/'replacements.csv').write_text('original,replacement,source\n/Users/alice/,/Users/user/,test\nAlice-style,X-style,test\n')
    (d/'blocklist.txt').write_text('# test\n\\bAlice\\b\n/Users/(?!user/)[A-Za-z]\n')
    a = Anonymizer(d)
    assert a.file('r.md', b'cd /Users/alice/x; Alice-style') == b'cd /Users/user/x; X-style'
    assert gzip.decompress(a.file('r.jsonl.gz', gzip.compress(b'/Users/alice/y'))) == b'/Users/user/y'
    assert a.file('b.png', b'\x89PNG Alice') == b'\x89PNG Alice'
    assert a.edited == {'r.md': 2, 'r.jsonl.gz': 1}
    assert [s for _, s in a.leaks('n.txt', b'by Alice at /Users/bob/')] == ['Alice', '/Users/b']
    assert a.leaks('ok.txt', b'/Users/user/z') == []


def test_changed_graphic_requires_visual_review_and_corrupt_graphic_fails(tmp_path):
    from PIL import Image
    a = _paper(tmp_path/'a', {'figures/p.png': b''})
    b = _paper(tmp_path/'b', {'figures/p.png': b''})
    Image.new('RGB', (3, 3), 'red').save(a/'figures/p.png')
    Image.new('RGB', (3, 3), 'blue').save(b/'figures/p.png')
    result = compare(a, b)
    assert result['status'] == 'PASS' and result['figure_review'] == ['figures/p.png']
    assert compare(a, b, strict_figures=True)['status'] == 'FAIL'
    (b/'figures/p.png').write_bytes(b'broken')
    assert compare(a, b)['differences'] == ['invalid-figure: figures/p.png']
