# Tested installation

Verified platform: CPython 3.13.11 / macOS arm64, using uv and isolated non-editable wheels. System TeX and pdftotext remain prerequisites. This is not a hermetic OS image or verification of every platform.

SciPy 1.16.3 replaced 1.15.3 on October 15, 2026: on macOS 27 the 1.15.3 arm64 wheel fails to load scipy.sparse.linalg (dyld rejects the zero-fill section of its _spropack extension).

The existing reviewed scientific wheelhouse contains the exact hashes in requirements-verified-macos-arm64-py313.txt. It is not distributed here. Canonical core also needs litellm, python-dotenv and their transitive dependencies: these must already be in the local uv cache for the offline route. The scientific wheelhouse alone is insufficient. Offline mode fails rather than downloading missing packages.

Given an existing interpreter, the reviewed wheelhouse, the cached core dependencies and benchmark source checked out at bef1775e7eaea6a5d5f3c41c829eb7cee55a0d9f:

```sh
uv venv --offline --python "$BASE_PYTHON" "$VENV"
PYTHON="$VENV/bin/python"
uv pip install --offline --python "$PYTHON" --no-index --find-links "$WHEELHOUSE" --require-hashes -r requirements-verified-macos-arm64-py313.txt
uv run --offline --no-project --python "$PYTHON" "$BENCHMARK_SOURCE/packages/fbsim-benchmark/tools/build_wheels.py" --offline --output "$LOCAL_WHEELS"
uv build --offline --no-sources --wheel --python "$PYTHON" --out-dir "$LOCAL_WHEELS" .
uv pip install --offline --no-sources --python "$PYTHON" --find-links "$WHEELHOUSE" --find-links "$LOCAL_WHEELS" --constraint requirements-observed.txt 'fbsim-core==0.1.0' 'fbsim-benchmark==0.3.0' 'forecastbench-sim-paper==0.3.0'
uv pip check --python "$PYTHON"
"$PYTHON" -m fbsim_paper smoke
"$PYTHON" -m pytest -q tests
```

Build from disposable source copies. Direct uv installation from the benchmark workspace can resolve editable workspace dependencies; use these named wheels. Verification checks installed import locations, absence of user/external site-packages, dependency consistency, and benchmark scorer hashes. Wheel hashes are platform-specific, not a universal lock. README gives a shorter index-enabled, editable installation route for users without the reviewed caches; it installs the benchmark packages from the pinned git revision instead of named wheels.

Hosted smoke CI tests the declared Python 3.11/3.13 support using the package runtime pins and compatible transitive dependencies. It deliberately does not apply the observed Python 3.13 environment constraints on Python 3.11: for example, observed contourpy 1.4.0 requires Python 3.12+. Hosted smoke is not evidence of a full build on either Linux environment.
