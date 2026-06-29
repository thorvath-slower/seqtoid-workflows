"""CZID-72 — S3-prefix work queue. Uses the S3-compatible store already configured for artifacts
(MinIO on self-hosted, real S3 on SaaS), so self-hosted needs no extra queue infrastructure.

Claim is atomic-enough for a single-replica runner: copy requests/<id>.json -> processing/<id>.json
then delete the original. (For multi-replica, swap this for a real lease; single replica is the
chart default — replicaCount: 1.)
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class S3RequestQueue:
    def __init__(self, client, cfg):
        self._s3 = client
        self._cfg = cfg

    def list_pending(self) -> list[str]:
        """Return request keys waiting under requests/ (oldest-first by key)."""
        cfg = self._cfg
        keys: list[str] = []
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=cfg.bucket, Prefix=cfg.requests_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".json"):
                    keys.append(key)
        return sorted(keys)

    def claim(self, request_key: str) -> str | None:
        """Move requests/<id>.json -> processing/<id>.json. Returns the new key, or None if already taken."""
        cfg = self._cfg
        name = request_key[len(cfg.requests_prefix):]
        processing_key = cfg.processing_prefix + name
        try:
            self._s3.copy_object(
                Bucket=cfg.bucket,
                CopySource={"Bucket": cfg.bucket, "Key": request_key},
                Key=processing_key,
            )
            self._s3.delete_object(Bucket=cfg.bucket, Key=request_key)
        except self._s3.exceptions.NoSuchKey:
            return None  # another iteration / replica already claimed it
        return processing_key

    def fetch(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self._cfg.bucket, Key=key)["Body"].read()

    def write_status(self, run_id: str, status: dict) -> None:
        import json

        key = f"{self._cfg.runs_prefix}{run_id}/status.json"
        self._s3.put_object(
            Bucket=self._cfg.bucket,
            Key=key,
            Body=json.dumps(status).encode(),
            ContentType="application/json",
        )

    def quarantine(self, processing_key: str) -> None:
        """Park a malformed/failed request out of the active prefixes so it is not retried forever."""
        cfg = self._cfg
        name = processing_key[len(cfg.processing_prefix):]
        self._s3.copy_object(
            Bucket=cfg.bucket,
            CopySource={"Bucket": cfg.bucket, "Key": processing_key},
            Key=f"failed/{name}",
        )
        self._s3.delete_object(Bucket=cfg.bucket, Key=processing_key)


def make_s3_client(cfg):
    """Lazily construct a boto3 S3 client (kept out of import path so pure modules test offline)."""
    import boto3

    return boto3.client("s3", endpoint_url=cfg.s3_endpoint, region_name=cfg.region)
