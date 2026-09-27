#!/usr/bin/env bash
# Copy the skills into a repository (travels to cloud sessions / Projects threads)
# or into ~/.claude/skills (this machine only).
#
#   scripts/install.sh --repo /path/to/your/repo [--force] [skill ...]
#   scripts/install.sh --user [--force] [skill ...]
#
# With no skill names, installs all skills under skills/.
set -euo pipefail

here="$(cd "$(dirname "$0")/.." && pwd)"
dest=""
force=0
names=()

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) dest="$2/.claude/skills"; shift 2 ;;
    --user) dest="$HOME/.claude/skills"; shift ;;
    --force) force=1; shift ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) names+=("$1"); shift ;;
  esac
done

if [ -z "$dest" ]; then
  echo "error: pass --repo PATH or --user" >&2
  exit 64
fi
if [ ${#names[@]} -eq 0 ]; then
  for d in "$here"/skills/*/; do names+=("$(basename "$d")"); done
fi

mkdir -p "$dest"
for n in "${names[@]}"; do
  src="$here/skills/$n"
  [ -f "$src/SKILL.md" ] || { echo "error: no skill named $n" >&2; exit 65; }
  if [ -e "$dest/$n" ]; then
    if [ "$force" -ne 1 ]; then
      echo "skip: $dest/$n exists (use --force to replace)"
      continue
    fi
    rm -rf "$dest/$n"
  fi
  cp -R "$src" "$dest/$n"
  find "$dest/$n" -name '__pycache__' -type d -prune -exec rm -rf {} +
  chmod +x "$dest/$n"/scripts/* 2>/dev/null || true
  echo "installed: $dest/$n"
done

case "$dest" in
  "$HOME/.claude/skills") echo "note: ~/.claude/skills does not reach cloud sessions. Use --repo for those." ;;
  *) echo "next: review, then commit .claude/skills in that repository so cloud sessions get it." ;;
esac
