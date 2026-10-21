# ForecastBench-Sim paper analysis

Cached analysis, aggregation, uncertainty summaries and plotting for ForecastBench-Sim. The cached routes check the scientific inputs and outputs of the **f214afe3 frozen analysis baseline**; the reporting code itself follows the current manuscript, whose generated files `fbsim-paper build` writes. See [manuscript mapping](docs/MANUSCRIPT_STATUS.md).

This repository is the home for the paper's analysis, including the combined-score, rank-table and Starsim scripts that used to live in the manuscript repository. Changes to paper analysis land here as pull requests. The cached routes check the f214afe3 baseline until new inputs are frozen into the data archive.

## What goes where

| Material | Home |
|---|---|
| Reusable world code: engines, question generation, forecast collection, scoring | [forecastbench-sim](https://github.com/forecastingresearch/forecastbench-sim) |
| Paper analysis: selection, normalization, aggregation, tables, figures | this repository, `src/` |
| How the paper's inputs were produced: production configs, seeds, prompts, model panels, producer scripts | this repository, [`production/`](production/README.md) |
| Manuscript text and the generated files it reads | the manuscript repository (Overleaf); `fbsim-paper build` writes the generated files |
| Inputs of the manuscript build: Micropolis's gathered forecasts, the model-name list, Starsim's pre-repair scores | private data archive: `datasets/paper-inputs` while the paper changes, frozen as `datasets/paper-inputs-YYYYMMDD` for each release |
| Raw provider responses, simulator outputs, datasets, human-subject records, credentials | private data archive, never Git |

## Install

Python 3.11+ is declared; the tested platform is CPython 3.13 / macOS arm64, and System TeX and `pdftotext` are needed for the figures. SciPy is pinned to 1.16.3 because the 1.15.3 macOS arm64 wheel no longer loads on macOS 27. The public benchmark supplies the numerical scorers; `install.sh` installs it at a pinned revision. Do not install the older standalone distribution alongside its two packages.

```sh
./install.sh      # creates .venv (or updates it) and runs fbsim-paper smoke
source .venv/bin/activate
pytest -q tests   # optional; needs no data archive
```

This repository is installed in editable mode, so commands run its scripts as checked out. After `source .venv/bin/activate` the `fbsim-paper` command is on the path (`python -m fbsim_paper` works too). `build_paper.sh` (see below) uses its own environment, `.venv-build`, with your forecastbench-sim checkout instead of the pinned benchmark. These commands need package-index access; for the verified non-editable wheel route and the offline wheelhouse route, see [environment](docs/ENVIRONMENT.md).

## Settings

Copy `.env.example` to `.env` (not committed) and set the paths in it. `fbsim-paper` reads `.env` from this checkout, else from the current directory, for each variable the shell has not set; command-line flags override both.

| Variable | What it is | Flag |
|---|---|---|
| `FBSIM_DATA_ROOT` | the data archive's `data/` folder (holding `datasets/` and `manifests/`) | `--data-root` |
| `FBSIM_PAPER_ROOT` | the manuscript checkout (the folder with `main.tex`), for `build` | `--paper-root` |
| `FBSIM_REPO_ROOT` | the forecastbench-sim checkout, for `build_paper.sh` | none |

## Working on the paper

`build` regenerates the manuscript's generated tables, figures, macros and data files in place, from this checkout's scripts:

```sh
fbsim-paper build                      # every step: micropolis, freeciv, starsim
fbsim-paper build micropolis starsim   # only these steps (always run in that order)
```

1. It refuses to run if the manuscript has uncommitted changes under `data/` or `figures/`, which it would overwrite; `--allow-dirty` overrides.
2. It copies each file of `$FBSIM_DATA_ROOT/datasets/paper-inputs` to the same path under the manuscript's `data/`, where the content differs. That folder is the working copy of the build's own inputs (the others are versioned archive folders, read in place); the manuscript keeps copies, so edit them in the archive, not in the manuscript.
3. It runs each step's scripts against the manuscript checkout, writing over the files they generate:
   - Micropolis: `analyze_paper.py`, from the gathered CSVs in `paper-inputs/micropolis`, including its cells of the shared cost tables.
   - FreeCiv: from the archived run (`freeciv-source`, run `run2_paper`), the backing files and README of `data/freeciv/`, the appendix tables, the per-forecast files, the reasoning-effort check, its cells of the shared cost, roster and validation tables, and the figures.
   - Starsim: `integrate_fixed_state.py`, from the cached calls and the fixed-state audit (`analysis-original`, `starsim-audit`). It also refits the combined score and the rank tables from all three worlds, so rerun it after changing Micropolis or FreeCiv. Then `build_metadata.py` fills Starsim's cells of the shared tables.
4. It prints `git status` of the manuscript's `data/` and `figures/`. Review the diff there and commit both repositories.

To use your forecastbench-sim checkout instead of the pinned benchmark, run `./build_paper.sh [steps]`, which takes the same arguments as `build`. It installs `fbsim-core` and `fbsim-benchmark` from `FBSIM_REPO_ROOT`, and this repository, as editable packages into `.venv-build`, then runs `fbsim-paper build`. `.venv-build` is separate from `.venv`, which keeps the pinned benchmark that `validate` and `reproduce` check. Reinstalling takes under a second when nothing changed. Use the script, or `uv pip`, rather than `uv sync` or `uv run`: those resolve the pinned benchmark packages from the package index, where they are not published.

There are no hash checks and no snapshot copy, so `build` works while code and inputs change; `validate` and `reproduce` are for frozen releases. Figures get a fixed PDF date (`SOURCE_DATE_EPOCH=0` unless set), so an unchanged figure leaves no diff. A full build takes about 2.5 minutes. Hand-written and frozen files are not generated: `openrouter_ids_table.tex`, `human_pilot_table.tex`, the `*_frozen.tex` validation tables and the schematic.

## Releasing a paper version (planned)

Not implemented yet; this is the agreed plan. When a version of the paper is released:

1. Commit and push the manuscript after a `fbsim-paper build` that leaves nothing to commit.
2. In the data archive, freeze `datasets/paper-inputs` as `datasets/paper-inputs-YYYYMMDD` and the manuscript commit as `datasets/paper-<commit>`, and add a manifest under `manifests/` with the SHA-256 of every file the build reads (the frozen inputs and the versioned folders it reads in place) and of the frozen manuscript, plus a `CHANGES.md` entry. Frozen folders are never edited afterwards.
3. Point `validate` and the reproduce commands at that manifest: they then build from the frozen inputs into a disposable copy of the frozen manuscript and compare every generated file with it. Until this happens, they target the f214afe3 release (see below).
4. Cut a new version of the archive bundle.

`datasets/paper-inputs` stays the working copy for the next version.

## Cached reproduction requires restricted external inputs

**The data and manifests are not distributed here, so a public clone cannot run these routes.** To regenerate the inputs from scratch, see [production/](production/README.md). Local availability does not grant redistribution rights. No download or data-release promise is made. With authorized access to the existing versioned private data home:

```sh
fbsim-paper validate
fbsim-paper reproduce --output "$NEW_STARSIM_OUTPUT"
fbsim-paper reproduce-freeciv --output "$NEW_FREECIV_OUTPUT"
fbsim-paper reproduce-micropolis --output "$NEW_MICROPOLIS_OUTPUT"
```

Each command takes `--data-root` or `FBSIM_DATA_ROOT` (see Settings). Each output directory must be new. Validation checks 487 frozen inputs and scorer hashes. Missing inputs fail explicitly. Routes read cached inputs and create disposable outputs; they do not rerun simulators, call models or edit the manuscript. Python network access is guarded. Archival helper scripts are not production entrypoints.

Starsim uses retained forecasts with repaired continuous truth; historical binary results remain appendix-only and excluded from the nine-cell combined score. FreeCiv consumes cached per-item/aggregate results; Micropolis consumes frozen gathered CSVs. `verification.json` distinguishes byte equality, PDF-text equality, numerical roundoff and layout differences. The known FreeCiv capability-figure annotation presence/placement mismatch remains; JSON roundoff is at most 4.22e-15 in the verified run. Do not replace frozen artifacts merely because a route succeeds.

**`reproduce` is expected to fail until the next paper release.** The scripts here now follow the manuscript (they match it at 2e57585, including its sign correction, rho(ECI, -loss)), while the cached routes still compare against the f214afe3 release. `reproduce` runs all 15 checks, records them in `verification.json` and exits nonzero if any fail: 4 do, the PNGs and PDF text of `fig_starsim_unconditional` and `fig_starsim_interventional`, whose annotations changed. Every data file it checks still matches f214afe3, and its Starsim and combined figures match the manuscript at 2e57585. `reproduce-freeciv` and `reproduce-micropolis` never fail on differences, but their comparisons drift the same way as their scripts change. All three are re-baselined when the next paper version is released (see "Releasing a paper version"). Until then, check out commit `7a00369` (the SciPy pin, the last commit where it passes) to rerun the passing f214afe3 verification.

See [limitations](docs/MIGRATION_GAPS.md), [boundaries](docs/BOUNDARIES.md), [attribution](docs/ATTRIBUTION.md), and the historical [results map](docs/results-map.yaml). Original histories and private data remain preserved separately.

See [historical production provenance](docs/PRODUCTION_PROVENANCE.md) for the bounded issue #6 audit: the pinned public runner is not the original paper producer, which is recorded in [production/](production/README.md). No numerical paper correction is indicated for those two specific defects; this does not establish general scientific correctness.
