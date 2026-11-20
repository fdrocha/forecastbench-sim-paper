#!/usr/bin/env bash
# Create .venv with the pinned benchmark (the environment of the normal build), this repository (editable)
# and the test dependencies. Reruns update it in place.
set -euo pipefail
REPO=$(cd "$(dirname "$0")" && pwd)
VENV="$REPO/.venv"
B=git+https://github.com/forecastingresearch/forecastbench-sim@bef1775e7eaea6a5d5f3c41c829eb7cee55a0d9f
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
