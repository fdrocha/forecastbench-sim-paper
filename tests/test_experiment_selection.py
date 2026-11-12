"""Additional datasets must not silently change the paper's instrument."""
import csv
from pathlib import Path
import runpy
import sys

import pytest

from fbsim_paper import build
from fbsim_paper.experiments import CONDITIONALS_ENV, include_micropolis_conditionals

ASSETS = Path(build.ASSETS)


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize("enabled,columns", [(False, 3), (True, 5)])
def test_combined_score_requires_explicit_opt_in(tmp_path, monkeypatch, enabled, columns):
    data = tmp_path / "data"
    models = ["invented-a", "invented-b", "invented-c"]
    write_csv(data / "model_names.csv", [dict(model=m, short_name=m) for m in models])
    write_csv(data / "freeciv/models_v2.csv", [dict(openrouter_id=m, name=m, eci=100+i) for i,m in enumerate(models)])
    write_csv(data / "micropolis/micropolis_model_scores.csv", [dict(model=m, mid_range_excess_brier=.1, tail_excess_bits=.2, excess_ncrps=.3) for m in models])
    write_csv(data / "freeciv/freeciv_results_wide.csv", [dict(model=m, bank_all_excess_brier=.1, tails_all_excess_bits=.2, continuous_all_excess_ncrps_global=.3, natcond_all_excess_t2=.4) for m in models])
    for study in ("natcond", "intcond"):
        write_csv(data / f"micropolis/micropolis_{study}_scores.csv", [dict(model=m, excess_t2=.5) for m in models])
    monkeypatch.setenv(CONDITIONALS_ENV, "1" if enabled else "0")
    monkeypatch.syspath_prepend(str(ASSETS / "combined"))
    monkeypatch.setattr(sys, "argv", ["combined_score.py", "--paper-root", str(tmp_path), "--out", str(tmp_path / "out/result.json")])
    loaded = runpy.run_path(str(ASSETS / "combined/combined_score.py"))
    assert {len(scores) for scores in loaded["MICRO"].values()} == {columns}


def test_default_build_overrides_ambient_opt_in(tmp_path, monkeypatch):
    paper, data = tmp_path / "paper", tmp_path / "data"
    paper.mkdir()
    (paper / "main.tex").write_text("synthetic manuscript")
    (data / build.INPUTS).mkdir(parents=True)
    monkeypatch.setenv(CONDITIONALS_ENV, "1")
    seen = []
    monkeypatch.setattr(build, "_commands", lambda *args: ({CONDITIONALS_ENV: "1"}, [["synthetic", "check.py"]]))
    monkeypatch.setattr(build.subprocess, "run", lambda *args, **kwargs: seen.append(kwargs["env"][CONDITIONALS_ENV]))
    build.run(["combined"], data, paper)
    build.run(["combined"], data, paper, include_conditionals=True)
    assert seen == ["0", "1"]


def test_invalid_experiment_setting_is_rejected(monkeypatch):
    monkeypatch.setenv(CONDITIONALS_ENV, "maybe")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        include_micropolis_conditionals()


def test_extended_build_does_not_run_nine_cell_diagnostic(tmp_path):
    for enabled in (False, True):
        _, commands = build._commands("combined", tmp_path, tmp_path, tmp_path, enabled)
        scripts = {Path(command[1]).name for command in commands}
        assert ("generalization.py" in scripts) is not enabled
        assert "external_benchmarks.py" in scripts
