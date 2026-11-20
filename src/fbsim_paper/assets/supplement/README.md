# ForecastBench-Sim: data supplement for review

This supplement lets you regenerate every generated table, figure and macro of the paper from its archived inputs.
It matches the manuscript at commit `{commit}`. The code is in two anonymized repositories:

- Benchmark code: https://anonymous.4open.science/r/forecastbench-sim-F142/
- Analysis code (the `fbsim_paper` package used below): https://anonymous.4open.science/r/forecastbench-sim-paper-8840/

## Regenerating the paper's results

Download both repositories (the Download button on each page, or
`https://anonymous.4open.science/api/repo/<name>/zip` with the names above) and unzip each into its own folder (the
zips have no top-level folder). The anonymized copy of `install.sh` cannot reach the benchmark's original location,
so install the benchmark from the downloaded copy, with `uv`, Python 3.13, TeX and `pdftotext` available:

```sh
cd analysis                                       # the folder holding the analysis repository
FBSIM_BENCHMARK_DIR="$PWD/../benchmark" bash install.sh   # the folder holding the benchmark repository
source .venv/bin/activate
```

Then, from this folder:

```sh
export FBSIM_DATA_ROOT="$PWD/data"
cp -R paper paper-rebuilt
fbsim-paper build --paper-root paper-rebuilt     # about 6 minutes; no simulators or model calls
fbsim-paper compare paper paper-rebuilt          # checks data and lists changed figures for visual review
```

`build` writes every generated file of the paper into `paper-rebuilt/`, from the inputs in `data/`. `paper/` holds
the paper's own copies of those files (its `data/` and `figures/`; the LaTeX source is not included, and `main.tex`
is a placeholder). `compare` checks them file by file: JSON files by value (numbers to 1e-12, ignoring `generated`
dates), PDFs ignoring embedded creation dates and producer, and data tables and other files byte for byte. Missing, extra, unreadable changed images, and data differences fail the check. A PASS can include figures listed under `figure_review`: inspect those for changes to labels, values or plotted marks. Linux and macOS can render identical inputs differently. Use `--strict-figures` to also fail on encoding or rendering differences.

## Contents

`data/datasets/` uses the layout of the authors' data archive, which the analysis code expects.

- `paper-inputs/`: the gathered Micropolis forecasts, scores and metadata, including
  `micropolis/continuous_replays.tar.gz` (the replay outcomes of the continuous questions), the model names, and
  Starsim's original paper scores.
- `freeciv-source/worlds/freeciv/fbsim_v3/`: the FreeCiv question sets of draw v1.8 with their replay truths and
  normalization constants (`sets/draw_v1/`), the eight turn-60 world reports (`reports/`), the per-item scores and
  summaries of the reported run (`results/run2_paper/`), the scores of the one-question-per-prompt and shuffled
  runs, and the raw responses that the reasoning-effort check and the case study read (`results/run2b_2026-09-20/`,
  `results/run2_effort/`, `results/run1_2026-09-09/elicit_medium/`).
- `freeciv-candidates/`: every question the FreeCiv generator enumerated before the draw, with replay truths, from
  which the FreeCiv baselines are computed.
- `freeciv-source-deliveries/`: the selection fractions of the draw (Appendix C) and the per-replay outcomes of the
  400 natural-conditional cells (`natcond-replays-20260923-v1/`).
- `micropolis-source-deliveries/.../results.tar.xz`: the Micropolis city runs, replay truths and scored results.
- `analysis-original/results/causal/`: the Starsim worlds and the archived model calls of the reported run
  (`rerun_lowest/`).
- `starsim-audit/production_v1/rescore/`: the fixed-state rescore of the Starsim continuous truths.
- `measles-case-study/`: the historical measles inputs of the case study; see its README.

## Not included

The paper's LaTeX source, the other raw model responses (all raw responses used in the analyses are in the published
data release; see Appendix F), the 92 GB of FreeCiv saved games, internal working files and diagnostic
plot images.

## Anonymization

Names, usernames, home-directory paths, repository links and the name of the authors' institution were replaced in
text files, including inside compressed files. `ANONYMIZED_FILES.csv` lists the edited files. No numbers were
changed. SHA-256 checksums of every file are in `SHA256SUMS.txt`.

## Licenses

See `LICENSE.md`: CC BY 4.0 for the data; the measles series derive from Project Tycho (CC BY 4.0); model outputs
remain subject to the providers' terms.
