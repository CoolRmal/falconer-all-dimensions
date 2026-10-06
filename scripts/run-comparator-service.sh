#!/usr/bin/env bash
set -euo pipefail

# Invoked by systemd after dropping privileges and blocking AF_UNIX.
task_root=$(cd "$(dirname "$0")/.." && pwd)
cd "$task_root"
export COMPARATOR_LANDRUN="$task_root/.tools/landrun/landrun"
export COMPARATOR_LEAN4EXPORT="$task_root/.tools/comparator/.lake/packages/lean4export/.lake/build/bin/lean4export"
mkdir -p .lake
"$COMPARATOR_LANDRUN" --best-effort --ro / --rw /dev --rwx "$task_root/.lake" \
  --rox /usr/bin --ldd --add-exec --env PATH --env HOME \
  -- /usr/bin/python3 scripts/security-preflight.py
exec lake env "$task_root/.tools/comparator/.lake/build/bin/comparator" \
  ComparatorChallenges/FalconerAllDimensions.json
