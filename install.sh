#!/usr/bin/env bash
# Usage: ./install.sh <dist-folder>

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <dist-folder>"
  exit 1
fi

SKILLS_DIR="$(cd "$(dirname "$0")/skills" && pwd)"
DIST_DIR="$(mkdir -p "$1" && cd "$1" && pwd)"

echo "[install] Skills source : $SKILLS_DIR"
echo "[install] Destination   : $DIST_DIR"

mkdir -p "$DIST_DIR"

for skill_path in "$SKILLS_DIR"/*/; do
  skill_name="$(basename "$skill_path")"
  link="$DIST_DIR/$skill_name"

  if [ -e "$link" ] || [ -L "$link" ]; then
    echo "[skip]    $skill_name  (already exists at $link)"
  else
    ln -s "$skill_path" "$link"
    echo "[linked]  $skill_name  ->  $link"
  fi
done

echo "[install] Done."
