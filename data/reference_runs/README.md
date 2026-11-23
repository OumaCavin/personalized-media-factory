# Reference runs

These JSON files are **measurement data published by the course authors**, copied
verbatim from the MIT licensed course repository:

- Repository: <https://github.com/DataTalksClub/production-ai-agents-for-media-generation>
- Pinned commit: `b417a3f5703b21b54514c85cfae9c749b57e08c5` (2026-11-19)
- Licence: MIT, Copyright (c) 2026 Nebius and DataTalks.Club
- Original location: `01-consistent-media-generation-on-serverless-gpus/assets/example_runs/`

They are included so that every number in this project can be re-derived by
running the analysis, instead of being copied by hand into prose. Each file has
a `<name>.provenance.json` sidecar describing where the measurement came from.

**These are not my own runs.** The environment this repository was authored in
has no GPU and no Nebius account, so no Job was executed here. Every document in
this repository labels numbers by provenance, and `mediagen analyze` prints a
warning whenever it reads a file whose provenance is not `own-run`.

Running the Job in `scripts/run_job.sh` on a Nebius account produces a metrics
file with `own-run` provenance, which replaces the reference data with no code
change.
