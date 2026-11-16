# Historical measles inputs of the case study

Inputs of the comparison in "Relevance to real-world forecasting" and its appendix. `fbsim-paper build` reads them
in its `case-study` step, which checks the saved scores and targets against the series and recomputes the
comparison and its figure.

- `timeseries/data/series/measles/*.json`: 1,339 historical state-season series (weekly state-level counts of
  reported measles cases, season-start years 1928–1962), each with the `history` shown to the models and the
  `future` used as outcomes. Derived from Project Tycho, US Measles 1888–2002, version 2.0
  (https://doi.org/10.25337/T7/ptycho.v2.0/US.14189004, CC BY 4.0).
- `timeseries/data/scores/*.csv`: 28 models' parsed forecasts and saved scores for the main `measles` stratum and
  the paired `measles_named` stratum (domain label shown), restricted to the same years. Rows are unchanged from the
  original evaluation outputs; other experimental strata are omitted.
- `measles-roster.json`: the historical evaluation's mapping from model IDs to ECI values, used only for secondary
  diagnostics. It differs from the simulator roster of the paper.
- `manifest.json`: SHA-256 checksums and row counts of these files.

The original model responses of this historical evaluation are not included. This is a selected retrospective
cohort (sufficiently large outbreaks, forecast origins before peaks), not a prospective evaluation.
