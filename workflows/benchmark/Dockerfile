# syntax=docker/dockerfile:1.4
# Jupyter Docker Stacks images are published to quay.io since 2023-10 (Docker Hub
# is frozen). Digest-pinned per CZID-4. This base is Ubuntu 24.04 / Python 3.13.
FROM quay.io/jupyter/scipy-notebook:2025-12-31@sha256:aebf73afaf983124e075904ec7856c4b511d0415d1275835a6f08704422ece9e
ARG DEBIAN_FRONTEND=noninteractive
USER 0
LABEL maintainer="CZID Team idseq-tech@chanzuckerberg.com"
LABEL description = "Image for benchmarking CZ ID workflows"

# 24.04 uses the deb822 sources layout (/etc/apt/sources.list.d/ubuntu.sources),
# so the old us-west-2 mirror rewrite of /etc/apt/sources.list no longer applies.
RUN echo 'APT::Install-Recommends "false";' > /etc/apt/apt.conf.d/98czid; \
    echo 'APT::Install-Suggests "false";' > /etc/apt/apt.conf.d/99czid

# pip is provided by the conda env (/opt/conda/bin/pip3); only jq is needed from apt.
RUN apt-get -qq update && apt-get -qq -y install \
    jq

COPY requirements-dev.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY benchmark_helpers benchmark_helpers
RUN pip3 install benchmark_helpers/

COPY notebooks notebooks/