"""CZID-72 — run-request model + validation. Pure (unit-testable offline).

A run request is a small JSON object dropped at s3://<bucket>/<requests_prefix><run_id>.json:

    {
      "run_id": "abc123",                # required, [A-Za-z0-9_-], used as a path segment
      "workflow": "consensus-genome",    # required, must resolve to <workflows_dir>/<workflow>/<workflow>.wdl
      "inputs": { ... }                  # required, miniwdl inputs JSON
    }
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_WORKFLOW_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class InvalidRunRequest(ValueError):
    """Raised when a request object is malformed — the request is quarantined, not retried forever."""


@dataclass(frozen=True)
class RunRequest:
    run_id: str
    workflow: str
    inputs: dict

    @classmethod
    def parse(cls, raw: bytes | str) -> "RunRequest":
        try:
            doc = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise InvalidRunRequest(f"not valid JSON: {exc}") from exc
        if not isinstance(doc, dict):
            raise InvalidRunRequest("top-level JSON must be an object")

        run_id = doc.get("run_id")
        workflow = doc.get("workflow")
        inputs = doc.get("inputs")

        if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id):
            raise InvalidRunRequest(f"run_id must match {_RUN_ID_RE.pattern!r}")
        # Block path traversal in the workflow name (it becomes a filesystem path).
        if not isinstance(workflow, str) or not _WORKFLOW_RE.match(workflow):
            raise InvalidRunRequest(f"workflow must match {_WORKFLOW_RE.pattern!r}")
        if not isinstance(inputs, dict):
            raise InvalidRunRequest("inputs must be a JSON object")

        return cls(run_id=run_id, workflow=workflow, inputs=inputs)
