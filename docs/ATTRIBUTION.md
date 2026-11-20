# License and attribution

This source export is distributed under GPL-3.0-only; see LICENSE. Preserve existing source headers and notices. Dependencies retain their respective licenses. This grant does not cover the data folder, raw provider responses, simulator engines or manuscript assets; the data folder carries its own licenses.

- Micropolis reporting/support derives from Fabio Rocha's source at 8c70972b698f079d54b8a2255c81fbefc55e7d99. The source root contains the preserved GPLv3 text.
- FreeCiv reporting derives from Jaeho Lee's source at 4e35dd20ebc64dbaec28839fafcb88561664e3e1; the run-2 analysis scripts added later come from daca5a15af759f4124960e30694bff15256b7f5d. The selection weights of the Appendix C comparison use Jaeho Lee's selection fractions (run/selection_fractions.py at daca5a15). The source root contains the same GPLv3 text. Neither source tree contains a competing nested license for the extracted code.
- Starsim and shared paper analysis derive from Nick Merrill's paper analysis at f214afe3. On 2026-09-24 the author expressly authorized the remaining paper-specific analysis/plotting code under the same GPL as ForecastBench-Sim, retaining third-party licenses and notices. Earlier permission also covered the separately extracted Starsim parsing/scoring routines. On 2026-10-15 the combined-score, rank-table and Starsim scripts were updated from the manuscript repository at 2e57585, where coauthors had continued editing them, and removed from it. No broader data rights are implied.
- `production/` holds byte-for-byte copies of the producers: Micropolis production settings from Fabio Rocha's source at 8c70972b698f079d54b8a2255c81fbefc55e7d99, Nick Merrill's Starsim producer code, runner patch and fixed-state audit, and Jaeho Lee's FreeCiv launchers, run records and replay environment from freeciv-v3 at daca5a15af759f4124960e30694bff15256b7f5d, released under the same GPL. Sources and hashes are in production/PROVENANCE.json.
- Packaging, the build and data-check commands, explicit path changes and disabled provider access were introduced during migration. Numerical Starsim/Micropolis scorers are imported from the separately pinned benchmark rather than copied here.

A production-setting comment in the Starsim roster loader was removed for the public export; its executable AST is unchanged. Other scientific Python source remains byte-identical to the reviewed paper home. Original source and history remain privately preserved; no original history is rewritten.

The inherited GPL text has SHA256 8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903.

The calibration package migrates the offline FreeCiv/measles case-study audit, retaining its statistical definitions and cohorts. The historical measles forecasts, series and model/ECI roster are in the data folder, not in this code release.
