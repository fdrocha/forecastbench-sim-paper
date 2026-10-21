#!/usr/bin/env bash
# Install the local forecastbench-sim checkout and this repository into .venv-build (editable), then run
# `fbsim-paper build` with the given arguments. .venv-build is separate from .venv, which keeps the pinned
# benchmark that validate and reproduce check. Settings come from the shell, else from .env:
# FBSIM_REPO_ROOT (the forecastbench-sim checkout), FBSIM_PAPER_ROOT and FBSIM_DATA_ROOT.
set -euo pipefail
REPO=$(cd "$(dirname "$0")" && pwd)
VENV="$REPO/.venv-build"

# .env fills only variables the shell has not set.
if [[ -f "$REPO/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)= ]] || continue
    [[ -n "${!BASH_REMATCH[1]+set}" ]] || eval "export $line"
  done < "$REPO/.env"
fi
: "${FBSIM_REPO_ROOT:?set FBSIM_REPO_ROOT, in the shell or $REPO/.env, to the forecastbench-sim checkout}"

[[ -d "$VENV" ]] || uv venv --python 3.13 "$VENV"
uv pip install --quiet --python "$VENV/bin/python" \
  -e "$FBSIM_REPO_ROOT/packages/fbsim-core" -e "$FBSIM_REPO_ROOT/packages/fbsim-benchmark" -e "$REPO"
exec "$VENV/bin/fbsim-paper" build "$@"
