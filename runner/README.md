# seqtoid-pipeline-runner (CZID-72)

Self-hosted **miniwdl-on-Kubernetes** pipeline runner. Replaces the AWS SWIPE / Step Functions +
Batch dispatch on the self-hosted appliance: each WDL task becomes a Kubernetes Job (miniwdl's
`kubernetes` backend) instead of an AWS Batch job, and artifacts read/write an S3-compatible store
(MinIO on self-hosted) so the WDL `s3://` paths are unchanged.

Deployed by the `seqtoid-pipeline-runner` Helm chart (`deploy/charts/seqtoid-pipeline-runner`), which
provides the Deployment, the config env, and the RBAC miniwdl needs to manage per-task Jobs.

## How it works

1. **Request queue = an S3 prefix.** A run request is a small JSON object dropped at
   `s3://<bucket>/requests/<run_id>.json` — so self-hosted needs **no extra queue infrastructure**
   (it reuses the MinIO already there). Format:
   ```json
   { "run_id": "abc123", "workflow": "consensus-genome", "inputs": { } }
   ```
2. **Claim** — the runner moves `requests/<id>.json` → `processing/<id>.json` (claim), then runs.
   Single-replica by default (`replicaCount: 1`); for multi-replica, swap the claim for a real lease.
3. **Dispatch** — `miniwdl run <workflows_dir>/<workflow>/<workflow>.wdl --input <inputs> --dir s3://.../runs/<id>/outputs`
   with the Kubernetes backend (from `MINIWDL__*` env).
4. **Status** — written to `s3://<bucket>/runs/<id>/status.json` (`running` → `succeeded`/`failed`).
   Malformed requests are quarantined to `failed/` (not retried forever).

## Config (env — set by the chart)

| Env | Meaning | Default |
|-----|---------|---------|
| `SEQTOID_WORKFLOWS_BUCKET` | artifact + queue bucket | *(required)* |
| `AWS_ENDPOINT_URL_S3` | S3 endpoint (MinIO); unset → real AWS S3 | unset |
| `AWS_REGION` | region | `us-east-1` |
| `RUNNER_WORKFLOWS_DIR` | where the WDL sources live | `/workflows` |
| `RUNNER_POLL_INTERVAL_SEC` | idle poll interval | `15` |
| `MINIWDL__SCHEDULER__BACKEND` | miniwdl backend | `kubernetes` (chart) |

## Tests

Pure-logic + orchestration tests run offline (stdlib only, no boto3/k8s/miniwdl):

```
python -m unittest discover -s runner/tests
```

## Status

First-cut implementation. End-to-end validation (a real miniwdl run dispatching k8s Jobs against a
cluster + MinIO) is the remaining integration step — see the miniwdl-on-k8s spike.
