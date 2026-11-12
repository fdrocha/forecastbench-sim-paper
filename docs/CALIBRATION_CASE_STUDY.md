# FreeCiv and historical measles calibration

`fbsim-paper case-study` reproduces the exploratory upper-quantile diagnostic in
“Relevance to real-world forecasting” (manuscript commit `86b46d1`). It reads retained
forecasts and historical outcomes, checks the saved measles scoring and targets,
computes calibration/uncertainty/sensitivities, and renders the two-bar figure.
It never calls providers, runs simulators, downloads inputs, or edits the manuscript.

## Private inputs

The inputs are not included in this repository or downloaded by the command.
Keep them, and the output directory, outside Git. This command is independent of
the frozen `validate` route and does not claim to validate the entire data archive.

- `--freeciv-root`: the retained `worlds/freeciv/fbsim_v3` directory containing
  `sets/draw_v1/continuous_300.json`,
  `results/run2_paper/results_v1/freeciv_results_wide.csv`, and
  `results/run2b_2026-09-20/batched/*/results.jsonl`.
- `--measles-root`: the historical evaluation's `experiments/timeseries` directory,
  containing `data/scores/*.csv` and `data/series/measles/*.json`.
  Scores must include the `measles` stratum and the smaller `measles_named` cohort
  for the paired domain-label sensitivity. Historical series files supply the
  original `history` and `future` arrays, independently checked against scored targets.
- `--measles-roster`: a private JSON object mapping the historical evaluation's
  canonical model IDs to ECI values, exported from its `experiments/eci_scores.py`
  `ECI_SCORES` dictionary. Do not substitute the current ICLR model roster: the
  cross-domain panels differ. ECI is used only in secondary descriptive diagnostics;
  some historical ECI entries are estimates. The mapping is also the canonical
  filename-to-model lookup used by the original audit. Its SHA-256 is recorded.

For example, with these paths set in your shell:

```sh
fbsim-paper case-study \
  --freeciv-root "$FREECIV_RETAINED_ROOT" \
  --measles-root "$HISTORICAL_TIMESERIES_ROOT" \
  --measles-roster "$HISTORICAL_MODEL_ROSTER" \
  --output "$NEW_CALIBRATION_OUTPUT"
```

Output must be new and outside all input directories and Git checkouts. A failed
run is left for inspection; it has no passing `run-status.json`. Use another new
output directory to rerun. The worker runs under the existing Python network guard.
The inputs are read-only; all generated arrays and receipts are private outputs.

To also check parsing against original responses, add:

```sh
  --freeciv-raw-repo "$RETAINED_FREECIV_GIT_CHECKOUT"
```

This needs `data/forecasts/<model-slug>/measles/<series-id>.json` under the measles
root, plus the archived FreeCiv `calls.jsonl.gz` in the specified Git checkout.
The default raw-call revision is `daca5a15af759f4124960e30694bff15256b7f5d`;
`--freeciv-raw-ref` overrides it explicitly. No Git fetch is performed. A run
without this option reports `parser_audit: NOT_RUN`, never a parser-audit pass.
The primary data are not silently repaired: the parser sensitivity excludes
forecasts whose quantiles cannot be independently recovered and matched.

## Definitions and expected results

The cohort and calculations retain the original audit's choices:

- FreeCiv: 24 models, 300 continuous questions, 8 worlds, 1,000 replays per question;
  60 questions at each of 30, 60, 90, 120 and 150 turns ahead.
- Measles: season-start years 1928–1962, at least 1,071 series per model (80% of
  the 1,339-series cohort, rounded up), and the historical roster (excluding `google/gemini-2.0-flash-lite-001`, as in the original audit).
  This selects 28 models, 7,942 series/horizon targets and 217,910 scored forecasts.
  At 20 weeks, only 1,247 series have outcomes; this is not a complete 1,339-series panel.
- Within each model and horizon, average available item exceedance probabilities;
  then average models equally. This is not a pooled forecast average.
- Strict `Y > p75` handles count ties; a calibrated 75th percentile has exceedance
  probability **at most** 25%. FreeCiv uses empirical replay probabilities and
  measles uses the single historical realization. There is no p90/p95 interpolation.
- The saved five-quantile measles pinball scores are recomputed, and each target is
  checked against its historical series. Missing forecasts remain missing.
- 10,000 bootstrap draws, seed 20261110: resample FreeCiv worlds, or measles
  season-start years and states separately, with each model's available-item
  denominator retained. Model panels are fixed; these are not joint uncertainty intervals.

The longest-horizon equal-model rates are **55.7776799617%** (FreeCiv) and
**82.3304288371%** (measles). World/year cluster intervals are approximately
49.5–60.8% and 80.2–84.3%; respectively 22/24 and 28/28 model estimates exceed 25%.
The paired labeled-measles subset gives 85.5% unlabeled versus 91.8% labeled at
20 weeks, with 84–247 pairs per model; all 28 labeled model estimates exceed 25%.

This is exploratory: the initial lower-quartile hypothesis failed in aggregate,
and the upper-quartile diagnostic emerged from the wider grid. The historical
cohort selects sufficiently large outbreaks and forecast origins before peaks
using complete seasons; the main histories are unlabeled. Named-context results
come from a smaller selected pilot, not a randomized context-effect estimate.
FreeCiv exceedance is not monotonic in horizon, and its family results differ.
Do not infer a common mechanism, live deployment failure rate, ranking transfer,
or improvement transfer from these results. Eight FreeCiv worlds also limit
uncertainty and generalization claims.

## Outputs and manuscript use

- `calibration-overview.csv`, `per-model-calibration.csv`, diagnostic NPZs and item
  metadata: all native quantiles, interval coverage, available/common-item panels.
- `cluster-intervals.csv`, `cluster-horizon-differences.csv`, `sensitivity.csv`,
  `per-cluster-calibration.csv`, `secondary-eci-correlations.csv`: uncertainty,
  leave-one sensitivities, stable-series sensitivity and secondary associations.
- `matched-context.csv`, `matched-context-summary.json`: paired domain-label results.
- Optional parser audit: JSON reports, confirmed-forecast masks, and sensitivity CSV.
- `calibration_case_study.csv` and `.pdf/.svg/.png`: two bars, 25% reference line,
  cluster intervals, label “FreeCiv / 150 turns ahead”; no embedded caption.
- Input and analysis-source hash manifests, `verification.json`, `uncertainty-method.json`,
  `run-config.json`, `run-status.json`: private provenance and completion receipts.

After review, the aggregate plot CSV corresponds to manuscript
`data/calibration_case_study.csv`, and the PDF to
`figures/calibration_case_study.pdf`. Copying those two reviewed artifacts is a
separate manuscript update; this command does not publish them. Never copy the
private arrays, source hashes, raw parsing excerpts or run receipts into Git.

`tests/test_calibration.py` uses synthetic data, so hosted CI needs no private
archive. Scientific code originated in the local offline calibration audit;
original script hashes and migration scope are in `CALIBRATION_SOURCE_MAPPING.json`.
The historical forecast collection and model roster are external inputs, not
newly distributed code or data.
