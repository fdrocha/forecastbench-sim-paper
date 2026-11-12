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

## Remaining release dependencies

This is not a newly frozen archive or a completed full reproduction. The
`validate` and `reproduce` commands deliberately retain their existing v1
manifests until a complete R&R input bundle can be checked and frozen.

The missing FreeCiv baseline inputs are
`datasets/freeciv-candidates/binary_candidates.csv` and
`datasets/freeciv-candidates/continuous_candidates.npz`, or the original
candidate banks plus their export provenance. Saved baseline summaries do not
replace independent regeneration from these inputs. These candidate pools
contain truths for unasked questions; under the archive policy they stay out of
Git and the public data package. Reviewer access and any distributable derived
material need to be arranged separately.

To finish the R&R freeze:

1. Add the missing inputs to the authorized private archive, update its
   `CHANGES.md`, and run `fbsim-paper check-archive` to preserve v1.
2. Build the default nine-cell manuscript in a disposable checkout and run the
   case study separately. Compare every generated result with the final
   manuscript, investigating differences rather than changing frozen inputs.
3. Follow the README's release procedure: retain the final manuscript snapshot,
   hash every required input/output, point the R&R reproduction routes at the
   new manifest, and freeze the new archive version. Keep v1 reproducible.
4. Refresh and verify the anonymized code repositories linked in the manuscript
   against the merged commits. Code merges do not establish mirror freshness or
   publish the private archive.
5. Prepare the reviewer supplement from approved materials and check its
   inventory. The author handles the PDF and supplementary upload to OpenReview.

The existing reviewer supplement includes raw model responses but not the
candidate export above. Its availability to reviewers is separate from the
promised public release of raw responses before publication.
