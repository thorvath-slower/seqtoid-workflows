#!/usr/bin/env bash
# CI/local harness for the vendored idseq-dag lib (used by the short-read-mngs,
# long-read-mngs and legacy-host-filter workflows). The lib had NO CI coverage,
# so it silently rotted on modern toolchains (invalid __version__, deprecated
# pkg_resources). This runs its portable green core unit suite so it can't rot
# unnoticed again.
#
# Scoped out (tracked in CZID-350): command_patterns' macOS /tmp
# path fragility, the deeper steps/* suites' collection errors, and migrating
# util/command.py off the deprecated pkg_resources.
#
# Usage:  lib/idseq-dag/run_idseq_dag_tests.sh   (PYTHON=python3.12 to pin)
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
echo ">> interpreter: $("$PY" --version 2>&1)"
venv="$(mktemp -d)/v"
"$PY" -m venv "$venv"
# shellcheck disable=SC1091
. "$venv/bin/activate"
pip install -q --upgrade pip
# editable install also exercises setup.py (validates the __version__ fix);
# setuptools provides pkg_resources (still used by util/command.py for now).
pip install -q -e . setuptools pytest

PYTHONPATH=. python -m pytest \
  tests/unit/util/test_parsing.py \
  tests/unit/util/test_log.py \
  tests/unit/util/test_trace_lock.py -q
