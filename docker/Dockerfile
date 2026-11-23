# The worker image for the Living Origin Cards run.
#
# One container, one GPU Job, ten animations. The image carries the code and the
# pinned Python dependencies and nothing else: the model weights are downloaded
# at run time, the records are baked in because they are tiny and part of the
# job definition, and the results are written to the mounted bucket.
#
# Build from the repository root, because the build context needs src/ and data/:
#   docker buildx build --platform linux/amd64 -f docker/Dockerfile -t living-origin-cards:0.1.0 .
FROM pytorch/pytorch:2.13.0-cuda13.0-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    HF_HOME=/cache/huggingface \
    PYTHONPATH=/app

WORKDIR /app

# The weights cache and the output mount both live here.
RUN mkdir -p /cache /data

COPY docker/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# The code, and the ten records it works on.
COPY src/mediagen /app/mediagen
COPY data/origins.csv /app/origins.csv

ENTRYPOINT ["python", "-m", "mediagen.worker"]
CMD ["--records", "/app/origins.csv", "--out", "/data/runs/batch", "--n", "10"]
