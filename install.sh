#!/usr/bin/env bash
# Usage: ./install.sh <dist-folder>
# Creates a symlink in <dist-folder> for each skill under ./skills/.
# Skips any skill that already has an entry with the same name in the destination.

# Exit immediately on error, treat unset variables as errors, propagate pipe failures
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <dist-folder>"
  exit 1
fi

# Resolve absolute paths so symlinks are not relative to the working directory
SKILLS_DIR="$(cd "$(dirname "$0")/skills" && pwd)"
DIST_DIR="$(mkdir -p "$1" && cd "$1" && pwd)"

echo "[install] Skills source : $SKILLS_DIR"
echo "[install] Destination   : $DIST_DIR"

mkdir -p "$DIST_DIR"

for skill_path in "$SKILLS_DIR"/*/; do
  skill_name="$(basename "$skill_path")"
  link="$DIST_DIR/$skill_name"

  # -e checks real files/dirs; -L catches broken symlinks that -e would miss
  if [ -e "$link" ] || [ -L "$link" ]; then
    echo "[skip]    $skill_name  (already exists at $link)"
  else
    ln -s "$skill_path" "$link"
    echo "[linked]  $skill_name  ->  $link"
  fi
done

echo "[install] Done."
