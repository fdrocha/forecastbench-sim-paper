"""Synthetic checks of the data folder's SHA256SUMS.txt."""
from fbsim_paper import datacheck


def test_write_then_check_reports_missing_changed_added(tmp_path):
    (tmp_path/'datasets/a').mkdir(parents=True)
    (tmp_path/'datasets/a/x.csv').write_text('1')
    (tmp_path/'datasets/a/y.csv').write_text('2')
    (tmp_path/'.DS_Store').write_text('')
    assert datacheck.write(tmp_path) == 2
    assert datacheck.check(tmp_path) == dict(files=2, missing=[], changed=[], added=[])
    (tmp_path/'datasets/a/x.csv').write_text('changed')
    (tmp_path/'datasets/a/y.csv').unlink()
    (tmp_path/'datasets/z.json').write_text('{}')
    assert datacheck.check(tmp_path) == dict(files=2, missing=['datasets/a/y.csv'], changed=['datasets/a/x.csv'],
                                             added=['datasets/z.json'])


def test_installed_scorers_match_pin():
    assert datacheck.pin() == []
