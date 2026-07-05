#!/usr/bin/env bash
#
# Keyless, offline ankora demo.
#
# Runs the full loop — run -> baseline set -> gate — using the deterministic
# `echo` provider and deterministic scorers only. NO network and NO API keys.
# It proves the gate exits 0 when clean and non-zero (1) when a Case regresses.
#
# Usage:  bash examples/run_demo.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Work on a copy so the repo stays clean.
cp "$HERE/demo/ankora.yaml" "$WORK/ankora.yaml"
mkdir -p "$WORK/evals"
cp "$HERE"/demo/evals/*.yaml "$WORK/evals/"

eg() { ( cd "$WORK" && uv run --project "$REPO" ankora "$@" ); }

echo "==> 1. Replay the suite (echo provider, no keys)"
eg run

RUN_ID="$(basename "$(ls -t "$WORK"/.ankora/runs/*.json | head -1)" .json)"
echo "    latest run: $RUN_ID"

echo "==> 2. Promote it to the baseline"
eg baseline set "$RUN_ID"

echo "==> 3. Gate against the baseline (clean — expect exit 0)"
set +e
eg gate
clean_exit=$?
set -e
echo "    clean gate exit code: $clean_exit"
if [ "$clean_exit" -ne 0 ]; then
  echo "FAIL: clean gate should have exited 0" >&2
  exit 1
fi

echo "==> 4. Deliberately break a Case (change its expected output)"
uv run --project "$REPO" python - "$WORK/evals/cairo.yaml" <<'PY'
import sys
import yaml

path = sys.argv[1]
with open(path) as fh:
    case = yaml.safe_load(fh)
case["reference"]["output"] = '{"city": "Atlantis", "country": "Nowhere"}'
with open(path, "w") as fh:
    yaml.safe_dump(case, fh, sort_keys=False)
print("    broke:", path)
PY

echo "==> 5. Gate again (regression — expect non-zero exit)"
set +e
eg gate
broken_exit=$?
set -e
echo "    broken gate exit code: $broken_exit"
if [ "$broken_exit" -eq 0 ]; then
  echo "FAIL: gate should have exited non-zero on a regression" >&2
  exit 1
fi

echo
echo "DEMO OK — clean gate exit=$clean_exit, broken gate exit=$broken_exit"
