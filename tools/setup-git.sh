#!/usr/bin/env bash
# setup-git.sh — one-time, OPT-IN setup to back your vault up to YOUR OWN git repo
# and (optionally) enable auto-push on every session-end.
#
# This template ships with NO git auto-push. Run this only if you WANT your own
# off-site backup. It:
#   1. starts a fresh git history in this folder (drops the template's history),
#   2. points 'origin' at the repo URL you give,
#   3. makes an initial commit and pushes it,
#   4. drops a local flag that turns on auto-push for vault-sync.
#
# Usage:
#   tools/setup-git.sh git@github.com:you/your-repo.git
#   tools/setup-git.sh https://github.com/you/your-repo.git --no-autopush   # backup but push manually
#
# Re-run any time to change the remote. To turn auto-push OFF later:
#   rm tools/.autopush-enabled
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REMOTE="${1:-}"
AUTOPUSH=1
[ "${2:-}" = "--no-autopush" ] && AUTOPUSH=0

if [ -z "$REMOTE" ]; then
  echo "Usage: tools/setup-git.sh <your-git-remote-url> [--no-autopush]"
  echo "Example: tools/setup-git.sh git@github.com:you/your-vault.git"
  exit 1
fi

cd "$ROOT" || { echo "ERR: cannot enter $ROOT"; exit 1; }

echo "This will start a FRESH git history in:"
echo "  $ROOT"
echo "and set 'origin' to:"
echo "  $REMOTE"
printf "Proceed? [y/N] "
read -r ans
case "$ans" in y|Y|yes|YES) ;; *) echo "aborted."; exit 0 ;; esac

# Fresh history so none of the template's commits carry over.
rm -rf .git
git init -q
git branch -M main 2>/dev/null || true
git remote add origin "$REMOTE"

git add -A
git commit -q -m "Initial commit — my AETHER OS vault" && echo "committed."

if [ "$AUTOPUSH" -eq 1 ]; then
  touch "$SCRIPT_DIR/.autopush-enabled"
  echo "auto-push ENABLED (vault-sync will push on session-end). Disable with: rm tools/.autopush-enabled"
else
  rm -f "$SCRIPT_DIR/.autopush-enabled"
  echo "auto-push left OFF (you'll push manually: git push)."
fi

echo "Pushing initial commit..."
if git push -u origin main; then
  echo "Done — your vault is backed up to $REMOTE"
else
  echo "Push failed (check the repo exists and you have access). Your commit is saved locally;"
  echo "fix access and run: git push -u origin main"
fi
