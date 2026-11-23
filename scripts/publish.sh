#!/usr/bin/env bash
# Create the GitHub repository and push this one to it.
#
# A personal access token is needed with the "repo" scope. It is read from the
# environment and never written to a file:
#
#   GIT_TOKEN=ghp_... ./scripts/publish.sh
#
# The token is only used for the API call and for the remote URL, and the
# remote URL is left with the token in it, the way git expects for a token
# authenticated remote.
set -euo pipefail

: "${GIT_TOKEN:?set GIT_TOKEN to a GitHub personal access token with the repo scope}"

OWNER="${OWNER:-OumaCavin}"
REPO_NAME="${REPO_NAME:-personalized-media-factory}"
DESCRIPTION="${DESCRIPTION:-Living Origin Cards: batch generative media on serverless GPUs, with the unit economics attached.}"
API="https://api.github.com"

echo "==> checking the token"
if ! curl -sf -H "Authorization: token $GIT_TOKEN" "$API/user" >/dev/null; then
  echo "GitHub rejected the token. Create a new one at https://github.com/settings/tokens" >&2
  echo "with the 'repo' scope, then run this script again." >&2
  exit 1
fi

echo "==> creating $OWNER/$REPO_NAME if it does not exist"
if curl -sf -H "Authorization: token $GIT_TOKEN" "$API/repos/$OWNER/$REPO_NAME" >/dev/null; then
  echo "    already exists"
else
  curl -s -X POST \
    -H "Authorization: token $GIT_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "$API/user/repos" \
    -d "{\"name\":\"$REPO_NAME\",\"description\":\"$DESCRIPTION\",\"private\":false,\"auto_init\":false}" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print('    created:',d.get('full_name') or d.get('message'))"
fi

echo "==> setting the remote"
git remote set-url origin "https://$GIT_TOKEN@github.com/$OWNER/$REPO_NAME.git"

echo "==> pushing"
git push -u origin main

echo
echo "==> done: https://github.com/$OWNER/$REPO_NAME"
