# ForecastBench-Sim paper analysis

Cached analysis, aggregation, uncertainty summaries and plotting for ForecastBench-Sim. The scientific inputs and reporting code reproduce the **f214afe3 frozen analysis baseline**, not the latest manuscript. See [manuscript mapping](docs/MANUSCRIPT_STATUS.md).

This repository is the home for the paper's analysis. Changes to paper analysis land here as pull requests. The cached routes keep reproducing the f214afe3 baseline until new inputs are frozen into the data archive.

## What goes where

| Material | Home |
|---|---|
| Reusable world code: engines, question generation, forecast collection, scoring | [forecastbench-sim](https://github.com/forecastingresearch/forecastbench-sim) |
| Paper analysis: selection, normalization, aggregation, tables, figures | this repository, `src/` |
| How the paper's inputs were produced: production configs, seeds, prompts, model panels, producer scripts | this repository, [`production/`](production/README.md) |
| Raw provider responses, simulator outputs, datasets, human-subject records, credentials | private data archive, never Git |

## Install and smoke test

Python 3.11+ is declared; fresh offline reproduction is verified on CPython 3.13.11 / macOS arm64. SciPy is pinned to 1.16.3 because the 1.15.3 macOS arm64 wheel no longer loads on macOS 27. The public benchmark supplies the numerical scorers. Use the exact benchmark revision below; do not install the older standalone distribution alongside its two packages.

```sh
git clone https://github.com/forecastingresearch/forecastbench-sim.git benchmark-source
git -C benchmark-source checkout 9e016b76f14f98c496da513c5c8aca1c2db535cd
uv venv --python 3.13 .venv
PYTHON="$PWD/.venv/bin/python"
uv run --no-project --python "$PYTHON" benchmark-source/packages/fbsim-benchmark/tools/build_wheels.py --output dist/wheels
uv build --no-sources --wheel --python "$PYTHON" --out-dir dist/wheels .
uv pip install --python "$PYTHON" --find-links dist/wheels --constraint requirements-observed.txt 'fbsim-core==0.1.0' 'fbsim-benchmark==0.3.0' 'forecastbench-sim-paper==0.3.0' -r requirements-test.txt
uv pip check --python "$PYTHON"
"$PYTHON" -m fbsim_paper smoke
"$PYTHON" -m pytest -q tests
```

The install provides an `fbsim-paper` command (`python -m fbsim_paper` works too). These install commands require package-index access unless the reviewed wheels are already available. See [offline installation](docs/ENVIRONMENT.md) for the tested wheelhouse route. System TeX and `pdftotext` are needed for cached figures.

## Cached reproduction requires restricted external inputs

**The data and manifests are not distributed here, so a public clone cannot run these routes.** To regenerate the inputs from scratch, see [production/](production/README.md). Local availability does not grant redistribution rights. No download or data-release promise is made. With authorized access to the existing versioned private data home:

```sh
"$PYTHON" -m fbsim_paper validate --data-root "$FBSIM_DATA_ROOT"
"$PYTHON" -m fbsim_paper reproduce --data-root "$FBSIM_DATA_ROOT" --output "$NEW_STARSIM_OUTPUT"
"$PYTHON" -m fbsim_paper reproduce-freeciv --data-root "$FBSIM_DATA_ROOT" --output "$NEW_FREECIV_OUTPUT"
"$PYTHON" -m fbsim_paper reproduce-micropolis --data-root "$FBSIM_DATA_ROOT" --output "$NEW_MICROPOLIS_OUTPUT"
```

Each output directory must be new. Validation checks 488 frozen inputs and scorer hashes. Missing inputs fail explicitly. Routes read cached inputs and create disposable outputs; they do not rerun simulators, call models or edit the manuscript. Python network access is guarded. Archival helper scripts are not production entrypoints.

Starsim uses retained forecasts with repaired continuous truth; historical binary results remain appendix-only and excluded from the nine-cell combined score. FreeCiv consumes cached per-item/aggregate results; Micropolis consumes frozen gathered CSVs. `verification.json` distinguishes byte equality, PDF-text equality, numerical roundoff and layout differences. The known FreeCiv capability-figure annotation presence/placement mismatch remains; JSON roundoff is at most 4.22e-15 in the verified run. Do not replace frozen artifacts merely because a route succeeds.

See [limitations](docs/MIGRATION_GAPS.md), [boundaries](docs/BOUNDARIES.md), [attribution](docs/ATTRIBUTION.md), and the historical [results map](docs/results-map.yaml). Original histories and private data remain preserved separately.

See [historical production provenance](docs/PRODUCTION_PROVENANCE.md) for the bounded issue #6 audit: the pinned public runner is not the original paper producer, which is recorded in [production/](production/README.md). No numerical paper correction is indicated for those two specific defects; this does not establish general scientific correctness.
