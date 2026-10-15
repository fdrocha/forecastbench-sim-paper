# Frozen analysis versus manuscript

The executable routes and immutable references target f214afe3c7ac7c4d7a00120197dc4fd512243d47. The historical results map was assembled against d13772cbe59215303b78586851b4b99b85cad7f0; its path hashes and equality claims concern frozen artifacts.

Read-only canonical source inspection on 2026-09-24 found manuscript commit 7e592657cd2f795a3e84afd9ea8b4389c0e6cd9f. This is an inspected revision, not a promise that the live manuscript has stopped changing.

- The sign correction at 42465af uses rho(ECI, minus loss), so positive means higher capability accompanies better forecasts. Since October 15, 2026 the maintained Starsim scripts include it: assets/combined and assets/starsim were updated from the manuscript at 2e57585d7ab60df87c8440448c226469ae6b0486, so `reproduce` no longer matches the frozen Starsim figures. This is expected until the next paper release re-baselines the cached routes; commit 7a00369 keeps the frozen code. Saved input scores and the nine-cell fit are unchanged.
- Human-pilot removal at 2302400 removed the compiled inclusion. Retained historical pilot source/table is not current compiled-manuscript coverage and no participant data is released here.
- `tab:micropolis-questions` and `tab:validation-full` no longer appear as labels in the inspected source. The former was replaced with a pointer to the question templates.
- Newer manuscript edits removed the ForecastBench table's CI(worlds) and n columns and rounded Micropolis rho. The manuscript now includes `data/validation_table_forecastbench_frozen.tex`; the cached route still reproduces the original frozen analysis table. Other protocol/appendix prose edits also postdate the baseline.

The historical map has 52 entries (41 maintained routes, nine static/authored entries and two unresolved historical generators). Those counts must not be described as coverage of the current manuscript. No scientific inputs, scoring, normalization, selection or uncertainty procedure was changed for publication.
