#!/usr/bin/env bash
set -euo pipefail

# Both pinned tools have Lean 4.34 sources; compile with the project's exact patch release.
task_root=$(cd "$(dirname "$0")/.." && pwd)
tools_dir="$task_root/.tools"
comparator_commit=d03acab154d269c06e60e4de7e4cc85deebff94b
exporter_commit=076e8e57707e813375e8f9da8bf989799ace9680
landrun_commit=811cfff51ceaf3d9843708aa6d22e9b84ccac8b4
toolchain=$(cat "$task_root/lean-toolchain")

checkout_commit() {
  local url=$1 destination=$2 commit=$3
  if [[ ! -d "$destination/.git" ]]; then
    git init "$destination"
    git -C "$destination" remote add origin "$url"
  fi
  git -C "$destination" fetch --depth 1 origin "$commit"
  git -C "$destination" checkout --detach "$commit"
  test "$(git -C "$destination" rev-parse HEAD)" = "$commit"
}

mkdir -p "$tools_dir"
checkout_commit https://github.com/leanprover/comparator.git "$tools_dir/comparator" "$comparator_commit"
checkout_commit https://github.com/Zouuup/landrun.git "$tools_dir/landrun" "$landrun_commit"
printf '%s\n' "$toolchain" > "$tools_dir/comparator/lean-toolchain"
(
  cd "$tools_dir/comparator"
  lake build comparator lean4export
  test "$(git -C .lake/packages/lean4export rev-parse HEAD)" = "$exporter_commit"
)
(
  cd "$tools_dir/landrun"
  go build -o landrun ./cmd/landrun/main.go
)

printf 'Comparator: %s\nlean4export: %s\nLandrun: %s\nToolchain: %s\n' \
  "$comparator_commit" "$exporter_commit" "$landrun_commit" "$toolchain"
