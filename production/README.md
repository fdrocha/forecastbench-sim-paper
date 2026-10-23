# Production recipes

How the paper's inputs were produced, from scratch: production configs, seeds, prompts, model panels and producer scripts. The package commands (`python -m fbsim_paper ...`) never run anything here. They start from the cached outputs in the private data archive.

Every file is a byte-for-byte copy of what ran; [PROVENANCE.json](PROVENANCE.json) gives each file's source and SHA-256. Scripts keep their original absolute paths (`/Users/elsehow/Projects/...`), and several check their inputs' hashes by those paths, so adjust paths in a working copy, not here. Nothing here has been rerun since the paper.

## Starsim

1. **Simulator.** `forecastingresearch/forecastbench-sim` at tag `paper-starsim-producer` (`65204aa59cfb9fa835cf5b2af8917e02e98a4f26`) plus [pandemic-runner-p_death.patch](starsim/pandemic-runner-p_death.patch). The patch was an uncommitted change in production: it adds the `p_death` argument the paper's no-death worlds pass. Public `main` lacks it. The patched `runner.py` hashes to `b921742a…`, the value the frozen fixed-state plan records.
2. **Worlds and forecasts.** [starsim/iclr-2026](starsim/iclr-2026) is the producer layout from `forecastingresearch/iclr-2026` (private; code unchanged since `3f55a91`, 16 Sep 2026). Put `forecastbench-sim` beside it, as `pyproject.toml` expects.
   - Worlds: `starsim_single/mine_single.py` (continuous, headline) and `starsim_causal/mine_worlds.py` / `mine_dose.py` (binary, appendix). Mined worlds are in `results/causal/data/worlds/` and `starsim_causal/worlds*.json`.
   - Forecasts: `results/causal/rerun_lowest/run_all.sh` is the paper's run (per-model lowest reasoning effort, three repetitions). It needs `OPENROUTER_API_KEY`. The model roster is `results/causal/data/models.csv`.
3. **Repaired continuous truth.** [starsim/fixed_state](starsim/fixed_state) is the fixed-state audit, in order: `smoke/` → `corrected_smoke/` → `production_v1/production.py` (driven by the frozen `PLAN.json`: 4,000 seeds, 16,000 branches) → `production_v1/rescore.py`. Its `rescore/` outputs are what `python -m fbsim_paper reproduce` reads (`datasets/starsim-audit/production_v1/rescore` in the data archive). `verify_uptake.py` and `verify_numeric.py` are independent checks; they produce no paper numbers.
4. **Tables and figures.** The cached route in `src/fbsim_paper`.

## Micropolis

The producer is Fabio Rocha's `fdrocha/forecastbench-sim` at `8c70972b698f079d54b8a2255c81fbefc55e7d99` (branch `micropolis`), with the engine from `fdrocha/MicropolisCore`; the exact engine commit used was not recorded. [micropolis](micropolis) holds that commit's production settings: run configs (the paper's are `configs/continuous.json5` and `configs/binary.json5`), model panels, prompt variants, batching ablations, prompt preambles and epilogues, model lists, knowledge-eval statements and `model_specs.json5`. The scripts that use them are in that commit's `worlds/micropolis/scripts`. Benchmark `main`'s `worlds/micropolis` is a port of that code and has not been tried with these configs. Paper CSVs are gathered by `src/fbsim_paper/assets/micropolis/scripts/gather_paper_data.py`.

## FreeCiv

The producer is Jaeho Lee's `freeciv-v3` branch of `forecastingresearch/forecastbench-sim` at `daca5a15af759f4124960e30694bff15256b7f5d`. Its reusable code (question generation, elicitation harness, scorers, replay fleet) is in forecastbench-sim's `worlds/freeciv/fbsim_v3`. [freeciv](freeciv) holds the launchers, run records and environment from that commit's `worlds/freeciv/fbsim_v3`, at the same relative paths:

- **Launchers.** `run/full_run.sh` and `launch.sh` (run 1), `launch_run2.sh` and `launch_v2.sh` (run 2), `launch_effort_v2.sh` (effort check), `smoke_run.sh`, `build_run2.sh` (scoring and tables), `finalize_run2.sh` (delivery into the paper), `rebuild_natcond_rows.py`.
- **Run records.** `run/ELICITATION.md`, `PREFLIGHT_prompts.md`, `PREFLIGHT_v2.md`, `RUN2_PLAN.md`, and `corpus_docs/family_specs_rev27_2026-09-04.json`. The paper reports run 2b, the batched arm in `results/run2b_2026-09-20/batched`, with the natural-conditional arm of `results/run2_2026-09-20/natcond` (`RUN2_PLAN.md`, sections F and G).
- **Replay fleet as run.** `fleet/pod_bundle/freeciv_world_as_run.patch` (applied to forecastbench-sim's `worlds/freeciv` since then), and the pod's `pyproject.toml`, `uv.lock` and `fbsim-core` copy.

The rest of that commit's files are in the private data archive at the same relative paths under `datasets/freeciv-source/worlds/freeciv/fbsim_v3`: the question sets of draw v1.8 with truth and the continuous normalization constants (`sets/draw_v1/`), the eight turn-60 reports the models read (`reports/seed*/turn_060_report.txt`), the model panels (`run/models_v1.csv`, `run/models_v2.csv`) and the replay run's corpus docs (`corpus_docs/`, including `CHANNEL_READINESS.md`, also at `run/` in the producer). The branch's `README.md`, `sets/draw_v1/README.md` and the selection fractions behind the inverse-selection weights (`sets/draw_v1/selection_fractions_bank_tails_mirrors.json`) are under `datasets/freeciv-source-deliveries/freeciv-v3-daca5a15-v1`.

Raw responses, per-item scores and replay outcomes are in the private data archive (`datasets/freeciv-source` and `datasets/freeciv-source-deliveries`). The per-world pickles were not committed and are not in the archive; the candidate questions in them are, as `datasets/freeciv-candidates-20261022` (exported by `src/fbsim_paper/assets/freeciv/export_candidates.py`). Analysis scripts behind the paper's FreeCiv numbers are in `src/fbsim_paper/assets/freeciv`.

## Not here

Raw provider responses, simulator outputs and caches, datasets, human-subject records and credentials. These stay in the private data archive and out of Git.
