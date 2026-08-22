#!/usr/bin/env bash
# finish_card.sh — commit and push one card's work, then prove it landed.
#
# Usage: ./finish_card.sh "P-XX: description from the card's Commit line"
#
# Exits 0 and says so when there is nothing to commit (that is information,
# not an error). Exits non-zero only when something actually failed.

set -uo pipefail

GIT_NAME="${CARD_GIT_NAME:-Fabricio Lombardi}"
GIT_EMAIL="${CARD_GIT_EMAIL:-flombardi2012@gmail.com}"
BRANCH="${CARD_BRANCH:-main}"

MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "usage: ./finish_card.sh \"P-XX: description\"" >&2
  exit 2
fi

case "$MSG" in
  P-*) ;;
  *) echo "refusing: message should start with the card id, e.g. \"P-09b: ...\"" >&2
     exit 2 ;;
esac

cd "$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "not inside a git repository" >&2; exit 2; }

# Identity is per-container and does not survive a new sandbox. Set it every
# time rather than discovering it is missing at commit.
git config user.name  "$GIT_NAME"
git config user.email "$GIT_EMAIL"

REMOTE_URL=$(git config --get remote.origin.url)

echo "== staging"
git add -A

if git diff --cached --quiet; then
  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git ls-remote origin "refs/heads/$BRANCH" 2>/dev/null | awk '{print $1}')
  echo
  echo "Nothing to commit — the working tree is clean."
  echo "  local  HEAD : ${LOCAL:0:7}  $(git log -1 --pretty=%s)"
  echo "  remote $BRANCH : ${REMOTE:0:7}"
  if [ "$LOCAL" = "$REMOTE" ]; then
    echo "  local and remote agree. This card's work was already committed,"
    echo "  or it was never built. Check that message 1 ran and produced files."
  else
    echo "  local and remote DIFFER — there are unpushed commits."
    echo "  run: git push origin $BRANCH"
  fi
  exit 0
fi

echo "== files in this commit"
git diff --cached --name-status

echo
echo "== committing"
git commit -m "$MSG" || { echo "commit failed" >&2; exit 1; }

echo
echo "== pushing"
git push origin "$BRANCH" || { echo "push FAILED — commit is local only" >&2; exit 1; }

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')

echo
echo "== verification (read back from the remote, not from the push output)"
echo "  local  HEAD : ${LOCAL:0:7}"
echo "  remote $BRANCH : ${REMOTE:0:7}"

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "  MATCH — $MSG is on $REMOTE_URL"
  exit 0
else
  echo "  MISMATCH — the push reported success but the remote does not agree." >&2
  exit 1
fi
