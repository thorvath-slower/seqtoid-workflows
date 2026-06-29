"""CZID-72 — runner configuration, read from the environment the Helm chart sets.

Pure (no boto3 / no k8s) so it is unit-testable offline.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bucket: str
    s3_endpoint: str | None
    region: str
    requests_prefix: str
    processing_prefix: str
    runs_prefix: str
    workflows_dir: str
    poll_interval_sec: int
    task_namespace: str | None
    task_service_account: str | None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Config":
        e = os.environ if env is None else env
        bucket = e.get("SEQTOID_WORKFLOWS_BUCKET", "").strip()
        if not bucket:
            raise ValueError("SEQTOID_WORKFLOWS_BUCKET is required")
        return cls(
            bucket=bucket,
            # AWS_ENDPOINT_URL_S3 is set for MinIO/self-hosted; unset => real AWS S3.
            s3_endpoint=(e.get("AWS_ENDPOINT_URL_S3") or None),
            region=e.get("AWS_REGION") or e.get("AWS_DEFAULT_REGION") or "us-east-1",
            requests_prefix=e.get("RUNNER_REQUESTS_PREFIX", "requests/"),
            processing_prefix=e.get("RUNNER_PROCESSING_PREFIX", "processing/"),
            runs_prefix=e.get("RUNNER_RUNS_PREFIX", "runs/"),
            workflows_dir=e.get("RUNNER_WORKFLOWS_DIR", "/workflows"),
            poll_interval_sec=int(e.get("RUNNER_POLL_INTERVAL_SEC", "15")),
            task_namespace=(e.get("MINIWDL__KUBERNETES__NAMESPACE") or None),
            task_service_account=(e.get("MINIWDL__KUBERNETES__SERVICE_ACCOUNT") or None),
        )
