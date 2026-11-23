#!/usr/bin/env bash
# Build the worker image and optionally push it to a registry.
#
# The Job can only pull an image from a registry, so a local build is not
# enough: push it before you run the Job.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${IMAGE:-living-origin-cards:0.1.0}"
PLATFORM="${PLATFORM:-linux/amd64}"

cd "$REPO_ROOT"

echo "==> building $IMAGE for $PLATFORM"
docker buildx build --platform "$PLATFORM" -f docker/Dockerfile -t "$IMAGE" .

if [[ "${PUSH:-0}" == "1" ]]; then
  if [[ -z "${REGISTRY:-}" ]]; then
    echo "PUSH=1 but REGISTRY is not set (for example REGISTRY=my-dockerhub-user)" >&2
    exit 1
  fi
  echo "==> pushing $IMAGE to $REGISTRY"
  docker tag "$IMAGE" "$REGISTRY/$IMAGE"
  docker push "$REGISTRY/$IMAGE"
  echo "==> set WORKER_IMAGE=$REGISTRY/$IMAGE before running scripts/run_job.sh"
fi
