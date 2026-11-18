#!/usr/bin/env bash
# Create .venv with the pinned benchmark that validate and reproduce check, this repository (editable)
# and the test dependencies. Reruns update it in place.
set -euo pipefail
REPO=$(cd "$(dirname "$0")" && pwd)
VENV="$REPO/.venv"
B=git+https://github.com/forecastingresearch/forecastbench-sim@9e016b76f14f98c496da513c5c8aca1c2db535cd
# FBSIM_BENCHMARK_DIR: install the benchmark from a local copy instead (e.g. a downloaded anonymized mirror).
if [[ -n "${FBSIM_BENCHMARK_DIR:-}" ]]; then
  PKGS=("$FBSIM_BENCHMARK_DIR/packages/fbsim-core" "$FBSIM_BENCHMARK_DIR/packages/fbsim-benchmark")
else
  PKGS=("fbsim-core @ $B#subdirectory=packages/fbsim-core" "fbsim-benchmark @ $B#subdirectory=packages/fbsim-benchmark")
fi

[[ -d "$VENV" ]] || uv venv --python 3.13 "$VENV"
uv pip install --python "$VENV/bin/python" --constraint "$REPO/requirements-observed.txt" \
  "${PKGS[@]}" -e "$REPO" -r "$REPO/requirements-test.txt"
"$VENV/bin/fbsim-paper" smoke
