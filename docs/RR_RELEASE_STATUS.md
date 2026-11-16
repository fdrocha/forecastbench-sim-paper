# ICLR 2027 R&R reproduction status

The manuscript revision checked for this integration is Overleaf commit
`b1447e1f06c09f39a3a1d760083d5e22d6f89e6d`. It uses the original nine-cell
combined score, with repaired Starsim continuous targets and historical Starsim
binary outcomes excluded. The additional Micropolis conditional studies are
available only through an explicit opt-in; they are not part of this R&R.

## Current build

`fbsim-paper build` retains nine cells even when extra conditional inputs or
generated files exist. `--include-micropolis-conditionals` runs the additional
studies and includes their cells in the combined score, validation/rank tables
and Micropolis figure. Standalone asset scripts use
`FBSIM_INCLUDE_MICROPOLIS_CONDITIONALS=1` for that opt-in. The held-out-world
diagnostic in `generalization.py` covers only the original nine cells. The
eleven-cell build skips it; any existing diagnostic files still describe the
original instrument and must not be presented as eleven-cell results.

The combined step now generates the external-benchmark table and macros used by
the manuscript, including partial correlations and finite-bootstrap counts.
The historical measles comparison is reproduced separately by
`fbsim-paper case-study`; see `CALIBRATION_CASE_STUDY.md`.

## Reviewer supplement

`fbsim-paper supplement` writes the anonymized supplement for OpenReview from the
archive and the manuscript checkout: every archive input that `fbsim-paper build`
reads (including the FreeCiv candidate export, the measles inputs and the raw
responses that the effort check and case study read), the items Appendix F
describes, and a snapshot of the manuscript's generated files. Reviewers rebuild
into a copy of that snapshot and check it with `fbsim-paper compare`. The other
raw model responses are posted before publication, as Appendix F states.

The `validate` and `reproduce` commands still target the v1 (f214afe3) release;
no new archive version is frozen during the R&R.
