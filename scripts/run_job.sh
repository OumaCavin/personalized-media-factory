#!/usr/bin/env bash
# Run the ten origin cards as one Nebius Serverless AI Job.
#
# One Job, one startup, one model load per model, ten animations, and the Job
# stops billing when it ends. This is the batch pattern: nobody waits for any
# single asset, so there is no reason to keep a server warm.
#
# Before the first run:
#   1. Build and push the image:   PUSH=1 REGISTRY=<user> scripts/build_image.sh
#   2. Set WORKER_IMAGE, BUCKET and RUN_ID in the environment.
#   3. Upload data/origins.csv to s3://$BUCKET/inputs/origins.csv
#
# REGION and PLATFORM default to eu-north1 and gpu-h100-sxm, which is where the
# course's reference measurements were taken and where the L40S Intel option
# lives. Spot prices are published per region, and a platform only appears
# when there is preemptible capacity for it, so check the live price for your
# own region before you commit to it.
set -euo pipefail

: "${WORKER_IMAGE:?set WORKER_IMAGE to the pushed image, for example my-user/living-origin-cards:0.1.0}"
: "${BUCKET:?set BUCKET to your Nebius Object Storage bucket name}"
RUN_ID="${RUN_ID:-job-001}"
N="${N:-10}"
PLATFORM="${PLATFORM:-gpu-h100-sxm}"
PRESET="${PRESET:-1gpu-16vcpu-200gb}"
REGION="${REGION:-eu-north1}"
DISK_SIZE="${DISK_SIZE:-500Gi}"
TIMEOUT="${TIMEOUT:-2h}"
# Preemptible GPUs are much cheaper but Compute can take them back. Use
# PRICE_MODE=on-demand for a fixed price that cannot be interrupted.
PRICE_MODE="${PRICE_MODE:-preemptible}"

case "$PRICE_MODE" in
  preemptible) PRICE_FLAGS=(--preemptible --follows-spot-price) ;;
  on-demand)   PRICE_FLAGS=(--on-demand) ;;
  *) echo "PRICE_MODE must be preemptible or on-demand" >&2; exit 1 ;;
esac

# Read the live spot price before creating anything. A platform only publishes
# a price when there is preemptible capacity for it in that region, so an
# empty answer is a capacity signal, not a missing price.
echo "==> checking the live preemptible price for $PLATFORM in $REGION"
if python3 -c "import mediagen" >/dev/null 2>&1; then
  python3 -m mediagen spot-price --platform "$PLATFORM" --region "$REGION" || true
  echo
  echo "    If that table is empty, there is no preemptible capacity for that"
  echo "    platform in that region right now. Pick another region or platform,"
  echo "    or check the Nebius console Capacity dashboard."
else
  echo "    (mediagen is not importable here, so the price was not checked)"
fi
echo

if [[ "${DRY_RUN:-1}" == "1" ]]; then
  echo "==> dry run only, set DRY_RUN=0 to create the Job for real"
  DRY_RUN_FLAG=(--dry-run)
else
  DRY_RUN_FLAG=()
fi

CMD="python -m mediagen.worker \
  --records /app/origins.csv \
  --out /data/runs/$RUN_ID \
  --n $N \
  --gpu 'NVIDIA H100 80GB HBM3' \
  --region $REGION \
  --platform $PLATFORM \
  --preset $PRESET \
  --billing $PRICE_MODE \
  --run-id $RUN_ID"

set -x
nebius ai job create \
  "${DRY_RUN_FLAG[@]}" \
  --name "$RUN_ID" \
  --image "$WORKER_IMAGE" \
  --platform "$PLATFORM" \
  --preset "$PRESET" \
  --disk-size "$DISK_SIZE" \
  "${PRICE_FLAGS[@]}" \
  --timeout "$TIMEOUT" \
  --restart-policy never \
  --volume "$BUCKET:/data:rw" \
  --container-command bash \
  --args "-c '$CMD'"
