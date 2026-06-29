# CZID-72 — seqtoid-pipeline-runner image (miniwdl-on-k8s).
# Built/pushed to the offline mirror / local registry on self-hosted (see chart image.repository, #10/#205).
FROM python:3.12-slim

# WDL tasks run as their own k8s Jobs (miniwdl kubernetes backend); the runner itself only needs the
# python toolchain + kubectl-less in-cluster config (miniwdl-k8s uses the mounted service-account token).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY seqtoid_pipeline_runner ./seqtoid_pipeline_runner
RUN pip install --no-cache-dir .

# The WDL sources live at RUNNER_WORKFLOWS_DIR (default /workflows). Provide them either by mounting a
# volume at /workflows, or by layering this image FROM it and `COPY workflows /workflows`. Kept out of
# this base image so the runner and the (large) workflow images version independently.
VOLUME ["/workflows"]

# Run as non-root.
RUN useradd --create-home --uid 10001 runner
USER 10001

ENTRYPOINT ["seqtoid-pipeline-runner"]
