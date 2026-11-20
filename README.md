# ForecastBench-Sim paper analysis

Analysis, aggregation, uncertainty summaries and plotting for the ForecastBench-Sim paper. `fbsim-paper build` regenerates every generated table, figure and macro of the manuscript from the paper's data folder.

This repository is the home for the paper's analysis, including the combined-score, rank-table and Starsim scripts that used to live in the manuscript repository. Changes to paper analysis land here as pull requests.

## What goes where

| Material | Home |
|---|---|
| Reusable world code: engines, question generation, forecast collection, scoring | [forecastbench-sim](https://github.com/forecastingresearch/forecastbench-sim) |
| Paper analysis: selection, normalization, aggregation, tables, figures | this repository, `src/` |
| How the paper's inputs were produced: production configs, seeds, prompts, model panels, producer scripts | this repository, [`production/`](production/README.md) |
| Manuscript text and the generated files it reads | the manuscript repository (Overleaf); `fbsim-paper build` writes the generated files |
| Questions, truths, model responses, scored forecasts and every input of `fbsim-paper` | the paper's data folder (published with the paper; see "Data" below), never Git |
| Human-subject records, credentials | neither Git nor the published data |

## Install

Python 3.11+ is declared; the tested platform is CPython 3.13 / macOS arm64, and System TeX and `pdftotext` are needed for the figures. SciPy is pinned to 1.16.3 because the 1.15.3 macOS arm64 wheel no longer loads on macOS 27. The public benchmark supplies the numerical scorers; `install.sh` installs it at a pinned revision. Do not install the older standalone distribution alongside its two packages.

```sh
./install.sh      # creates .venv (or updates it) and runs fbsim-paper smoke
source .venv/bin/activate
pytest -q tests   # optional; needs no data folder
```

This repository is installed in editable mode, so commands run its scripts as checked out. After `source .venv/bin/activate` the `fbsim-paper` command is on the path (`python -m fbsim_paper` works too). `build_paper_dev.sh` (see below) uses its own environment, `.venv-build`, with your forecastbench-sim checkout instead of the pinned benchmark. These commands need package-index access; for the verified non-editable wheel route and the offline wheelhouse route, see [environment](docs/ENVIRONMENT.md).

## Settings

Copy `.env.example` to `.env` (not committed) and set the paths in it. `fbsim-paper` reads `.env` from this checkout, else from the current directory, for each variable the shell has not set; command-line flags override both.

| Variable | What it is | Flag |
|---|---|---|
| `FBSIM_DATA_ROOT` | the data folder (holding `datasets/` and `SHA256SUMS.txt`) | `--data-root` |
| `FBSIM_PAPER_ROOT` | the manuscript checkout (the folder with `main.tex`), for `build` | `--paper-root` |
| `FBSIM_REPO_ROOT` | the forecastbench-sim checkout, for `build_paper_dev.sh` | none |

## Working on the paper

`build` regenerates the manuscript's generated tables, figures, macros and data files in place, from this checkout's scripts:

```sh
fbsim-paper build                      # every step: micropolis, freeciv, starsim, combined, case-study
fbsim-paper build micropolis combined  # only these steps (always run in that order)
fbsim-paper build micropolis combined --include-micropolis-conditionals  # optional eleven-cell experiments
```

The default preserves the ICLR R&R nine-cell instrument. The explicit flag runs the Micropolis natural- and interventional-conditional studies and includes their scores and plots. For standalone asset scripts, set `FBSIM_INCLUDE_MICROPOLIS_CONDITIONALS=1` to opt in; otherwise they retain nine cells. These extra studies are not part of the ICLR R&R version, and their data (`micropolis-natcond`, `micropolis-intcond`) is not in the published data folder: the flag needs a data root that holds them (the archive keeps them in `private-data/datasets/`). The held-out-world diagnostic (`generalization.py`) covers only the nine cells, so the eleven-cell build skips it; its existing files still describe the nine-cell instrument.

1. It refuses to run if the manuscript has uncommitted changes under `data/` or `figures/`, which it would overwrite; `--allow-dirty` overrides.
2. It copies each file of `$FBSIM_DATA_ROOT/datasets/paper-inputs` to the same path under the manuscript's `data/`, where the content differs. The other data folders are read in place; the manuscript keeps copies of `paper-inputs`, so edit them in the data folder, not in the manuscript. It warns if the installed scorers differ from the benchmark pin.
3. It runs each step's scripts against the manuscript checkout, writing over the files they generate. Every table is written whole; nothing reads or edits a `.tex` file.
   - Micropolis: `analyze_paper.py`, from the gathered CSVs in `paper-inputs/micropolis`: macros, appendix tables, figures and the CSVs in `data/micropolis/`; `micropolis_baselines.py`, run first, scores the baselines (`data/micropolis/micropolis_baselines.json`), which the capability figure and the per-model table draw. `micropolis_natcond.py`, run next, before `analyze_paper.py`, scores the natural conditionals from `micropolis-natcond` (draw and model answers), with the binary base rates for the independence baseline: `fig_micropolis_natcond.pdf`, `micropolis_natcond_blocks.tex`, `micropolis_natcond_macros.tex` and, in `data/micropolis/`, the per-model scores and a summary. Each model is scored on the cells it answered at both turns, and every output reports the coverage. `micropolis_intcond.py`, run after it, scores the interventional conditionals from `micropolis-intcond` the same way, against P(A | do X): `fig_micropolis_intcond.pdf`, `micropolis_intcond_blocks.tex`, `micropolis_intcond_macros.tex` and, in `data/micropolis/`, the per-model scores and a summary. `analyze_paper.py` draws both summaries' turn-2 excess Brier in the capability figure's second row, and the combined step adds them to the validation tables, the combined score and the rank tables.
   - FreeCiv: from the archived run (`freeciv-source`, run `run2_paper`): the backing files of `data/freeciv/`, the appendix tables, the per-forecast files, the comparison with one question per prompt (`make_freeciv_grouping.py`), the reasoning-effort check, the validation statistics, the figures and the prose macros (`make_freeciv_macros.py`). `selection_weights.py` turns Jaeho Lee's selection fractions (`freeciv-source-deliveries`) into selection weights for the mid-range questions (`data/freeciv/freeciv_selection_weights.csv`), with which `make_freeciv_macros.py` writes the Appendix C comparison with equal weights. `make_freeciv_baselines.py`, run first, scores the baselines from the generator's candidate questions (`freeciv-candidates`, exported once from the generator's pickles by `export_candidates.py`) and the turn-60 reports. The candidates hold the truth of questions that were never asked; they are released with the paper, so future draws should use new candidate banks.
   - Starsim: `integrate_fixed_state.py`, from the cached calls and the fixed-state audit (`analysis-original`, `starsim-audit`): Starsim's scores, appendix tables and figures; `starsim_baselines.py`, run first from the audit's outputs, scores the baselines and the SIR forecast (`data/starsim/starsim_baselines.json`), which its figure and table draw.
   - Combined: from the other three steps' files in the manuscript's `data/`, `refit_combined.py` refits the combined score (with its figure, the rank tables, the fixed-state uncertainty table and the Appendix C sensitivity macros), `simulator_scores.py` fits the same score per simulator and writes their correlation table, `generalization.py` refits it on disjoint halves of the worlds and with each simulator held out (Appendix C's held-out worlds and simulators table; it also reads FreeCiv's per-item scores from `freeciv-source`), `external_benchmarks.py` writes the Appendix E.2 table and macros for FutureEval, Prophet Arena and ForecastBench from `model_scores.csv`; `make_roster_table.py` and `make_validation_tables.py` write the roster and the two validation tables (the ForecastBench one with the partial correlations given ECI from `partial_correlations.py`), and `make_baseline_table.py` writes the baselines' prose macros and the appendix tables of binary and continuous alternatives. Rerun it after changing any world. `external_correlations.py` is an earlier diagnostic using `external_scores.csv`; the manuscript table is generated by `external_benchmarks.py`.
   - Case study: runs `fbsim-paper case-study` on the archive's inputs (`freeciv-source`, `measles-case-study`) in a temporary directory and, if it passes, copies only `data/calibration_case_study.csv` and `figures/calibration_case_study.pdf` to the manuscript. Its other outputs are discarded; run `case-study` itself to keep them.
4. It prints `git status` of the manuscript's `data/` and `figures/`. Review the diff there and commit both repositories.

The normal build runs in `.venv`, which `install.sh` makes with the benchmark pinned to a forecastbench-sim commit (`install.sh`, `src/fbsim_paper/assets/benchmark-pin.json`). To see the effect of a scorer change in your forecastbench-sim checkout before moving the pin, run `./build_paper_dev.sh [steps]`, which takes the same arguments as `build`. It installs `fbsim-core` and `fbsim-benchmark` from `FBSIM_REPO_ROOT`, and this repository, as editable packages into `.venv-build`, then runs `fbsim-paper build`; the build warns that it is not pinned when the scorers differ. Reinstalling takes under a second when nothing changed. Use the script, or `uv pip`, rather than `uv sync` or `uv run`: those resolve the pinned benchmark packages from the package index, where they are not published.

`build` does not check input hashes, so it works while code and inputs change; `check-data` does (see "Data"). Figures get a fixed PDF date (`SOURCE_DATE_EPOCH=0` unless set), so an unchanged figure leaves no diff. A full build takes about 7 minutes. Hand-written files are not generated: `openrouter_ids_table.tex`, `human_pilot_table.tex` and the schematic. Generated files carry no review markup: when a generated table or figure changes visibly, note it in its caption in the manuscript with `\changenote`.

## Historical forecasting case study

`fbsim-paper case-study` reproduces the FreeCiv/measles upper-quantile comparison
from the retained forecasts, including bootstrap intervals, matched domain-label
sensitivity and the manuscript chart. It writes to a new directory, with
networking disabled; input paths not given default to the data folder's copies under `--data-root`.
`--parser-audit` also re-parses the raw FreeCiv and measles replies and checks them against the saved forecasts.
`build case-study` delivers only the chart's CSV and PDF to the manuscript. See [inputs, commands and limitations](docs/CALIBRATION_CASE_STUDY.md).

## Supplement for reviewers

`fbsim-paper supplement` writes the anonymized data supplement for OpenReview, as a folder and a zip named after the manuscript commit, beside the data archive (`--out` to choose; it never overwrites). It holds every data-folder input that `build` reads (without the model replies), the further items Appendix F describes, and a snapshot of the manuscript's generated `data/` and `figures/` (no LaTeX source). It applies the replacements in the anonymization folder (`--anonymization`; by default `private-data/datasets/supplement-anonymization` beside the data folder, which is not published), fails if a blocklisted string remains or the zip exceeds 95 MB (`--max-mb`), and refuses a manuscript with uncommitted generated files (`--allow-dirty`). Build the manuscript and commit its output first, so the snapshot matches a rebuild.

Reviewers rebuild into a copy of the snapshot and check it with `fbsim-paper compare paper paper-rebuilt` (JSON by value to 1e-12, ignoring `generated` dates; PDFs without embedded metadata; data tables byte for byte; changed graphics listed for visual review under `figure_review`). A PASS can include graphics requiring inspection (use `--strict-figures` to fail on rendering or encoding changes). The anonymized code mirror rewrites the benchmark's GitHub URL, so they install it from the downloaded anonymized benchmark repository: `FBSIM_BENCHMARK_DIR=<its folder> ./install.sh`.

## Data

The data folder holds everything the commands read, everything in the reviewer supplement, and every model
response behind the paper's results. It is released under CC BY 4.0 (its `LICENSE`); its `README.md` describes each dataset and the notice for
model responses, and its `licenses/` holds the simulators' and data sources' licenses.
`SHA256SUMS.txt` at its top lists every other file:

```sh
fbsim-paper check-data           # missing, changed and added files, and scorers that differ from the pin; exits nonzero on any
fbsim-paper check-data --write   # rewrite SHA256SUMS.txt after a deliberate change to the data
```

The commands read cached inputs only: they do not rerun simulators, call models or download anything. To regenerate
the inputs from scratch, see [production/](production/README.md).

Every model response behind the paper's results is in the data folder, except:

- **Micropolis batching ablation:** six of Llama 4 Scout's replies are missing. In the 50-question setting, the
  replies behind 300 of its 1,000 forecasts were overwritten after scoring by a later run that shared their prompts;
  the forecasts are in the scored results.
- **FreeCiv:** some replies are empty because the model ran to its output limit (Kimi K2 26 and DeepSeek V4 Flash
  26 to 27 in run 1, and 10 in DeepSeek V4 Flash's rerun).
- **Starsim:** 139 of the 5,184 planned calls failed without a reply (Kimi K2 has 182 of 216, DeepSeek V4 Flash 111).

## Releasing a paper version

1. Run `fbsim-paper build` until it leaves nothing to commit, then commit and push the manuscript.
2. Bring the data folder up to date (its `README.md` too), run `fbsim-paper check-data --write`, and check that a
   build from it into a clean manuscript checkout passes `fbsim-paper compare` against the committed manuscript.
3. Tag this repository and publish the data folder; from then on that published copy is the version's data.

See [boundaries and limitations](docs/BOUNDARIES.md) and [attribution](docs/ATTRIBUTION.md).

See [historical production provenance](docs/PRODUCTION_PROVENANCE.md) for the bounded issue #6 audit: the pinned public runner is not the original paper producer, which is recorded in [production/](production/README.md). No numerical paper correction is indicated for those two specific defects; this does not establish general scientific correctness.
