"""CZID-72 — orchestration: claim a request, run miniwdl with the Kubernetes backend, record status."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile

from .run_request import InvalidRunRequest, RunRequest

log = logging.getLogger(__name__)


def workflow_wdl_path(cfg, workflow: str) -> str:
    """Resolve <workflows_dir>/<workflow>/<workflow>.wdl, confined to workflows_dir (no traversal)."""
    base = os.path.realpath(cfg.workflows_dir)
    candidate = os.path.realpath(os.path.join(base, workflow, f"{workflow}.wdl"))
    if not candidate.startswith(base + os.sep):
        raise InvalidRunRequest(f"workflow path escapes workflows_dir: {workflow!r}")
    return candidate


def build_miniwdl_command(cfg, req: RunRequest, inputs_path: str) -> list[str]:
    """The miniwdl invocation. Backend/namespace come from MINIWDL__* env (set by the chart)."""
    out_uri = f"s3://{cfg.bucket}/{cfg.runs_prefix}{req.run_id}/outputs"
    cmd = [
        "miniwdl",
        "run",
        workflow_wdl_path(cfg, req.workflow),
        "--input",
        inputs_path,
        "--dir",
        out_uri,
        "--no-color",
        "--error-json",
    ]
    return cmd


class Runner:
    def __init__(self, cfg, queue, run_subprocess=subprocess.run):
        self._cfg = cfg
        self._queue = queue
        self._run_subprocess = run_subprocess

    def process_one(self, request_key: str) -> bool:
        """Claim + run a single request. Returns True if something was processed."""
        processing_key = self._queue.claim(request_key)
        if processing_key is None:
            return False

        try:
            req = RunRequest.parse(self._queue.fetch(processing_key))
        except InvalidRunRequest as exc:
            log.error("quarantining malformed request %s: %s", request_key, exc)
            self._queue.quarantine(processing_key)
            return True

        self._queue.write_status(req.run_id, {"run_id": req.run_id, "state": "running"})
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
                json.dump(req.inputs, fh)
                inputs_path = fh.name
            cmd = build_miniwdl_command(self._cfg, req, inputs_path)
            log.info("run %s: %s", req.run_id, " ".join(cmd))
            result = self._run_subprocess(cmd, capture_output=True, text=True)
            state = "succeeded" if result.returncode == 0 else "failed"
            self._queue.write_status(
                req.run_id,
                {"run_id": req.run_id, "state": state, "returncode": result.returncode},
            )
            if state == "failed":
                log.error("run %s failed (rc=%s): %s", req.run_id, result.returncode, result.stderr[-2000:])
        except Exception:  # noqa: BLE001 — record then re-raise so the loop can decide
            self._queue.write_status(req.run_id, {"run_id": req.run_id, "state": "error"})
            raise
        finally:
            try:
                os.unlink(inputs_path)
            except OSError:
                pass
        return True
