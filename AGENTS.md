Read README.md, workflow.yaml and docs/BOUNDARIES.md. Use documented offline smoke/validate commands. `fbsim-paper build` overwrites generated files in the manuscript checkout; run it only when asked. Never implicitly run simulators, model APIs, downloads or production helpers. Never alter frozen data, normalization, panels or scores to make checks pass. Keep credentials, raw provider responses, datasets and personal or human-subject records out of files and Git ancestry. Production settings and producer scripts belong in production/, byte-for-byte with provenance. Preserve attribution and source hashes. Manuscript and data publication are separate tasks.

Releases follow the README's "Releasing a paper version".

Data archive: each paper version has its own frozen version of the archive (v1 for the ICLR submission; v2 next); the working copy is the one `FBSIM_DATA_ROOT` points at.
- Never edit, move or delete a v1 file (those listed in the archive's `metadata/SHA256SUMS.txt`), so v1's code still runs on the working archive. If a v1 file needs a different version, add it at a new path.
- Files added since v1 are edited, overwritten or deleted in place as the paper changes; keep no interim versions and use no dated folder names. Change them only when asked, and report every deletion.
- The archive's `CHANGES.md` describes how it differs from v1 now, not a history: update it whenever that difference changes. Hashes are recorded only when a version is frozen.
- `fbsim-paper check-archive` checks the v1 files and lists what was added since v1; run it after changing the archive.
- The archive is private, not a public or reviewer release; a public package needs its own review and must leave out `datasets/freeciv-candidates`.
