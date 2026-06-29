"""CZID-72 — offline unit tests for the runner's pure logic + orchestration (no boto3/k8s/miniwdl).

Run: `python -m unittest discover -s runner/tests` (stdlib only — no pytest/boto3 needed).
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from seqtoid_pipeline_runner.config import Config  # noqa: E402
from seqtoid_pipeline_runner.run_request import InvalidRunRequest, RunRequest  # noqa: E402
from seqtoid_pipeline_runner import runner as runner_mod  # noqa: E402


def _cfg(**over):
    base = dict(
        bucket="b", s3_endpoint=None, region="us-east-1", requests_prefix="requests/",
        processing_prefix="processing/", runs_prefix="runs/", workflows_dir="/workflows",
        poll_interval_sec=15, task_namespace=None, task_service_account=None,
    )
    base.update(over)
    return Config(**base)


class TestConfig(unittest.TestCase):
    def test_requires_bucket(self):
        with self.assertRaises(ValueError):
            Config.from_env({})

    def test_endpoint_and_region_defaults(self):
        c = Config.from_env({"SEQTOID_WORKFLOWS_BUCKET": "wf"})
        self.assertEqual(c.bucket, "wf")
        self.assertIsNone(c.s3_endpoint)          # unset => real AWS S3
        self.assertEqual(c.region, "us-east-1")

    def test_minio_endpoint(self):
        c = Config.from_env({"SEQTOID_WORKFLOWS_BUCKET": "wf", "AWS_ENDPOINT_URL_S3": "http://minio:9000"})
        self.assertEqual(c.s3_endpoint, "http://minio:9000")


class TestRunRequest(unittest.TestCase):
    def test_valid(self):
        req = RunRequest.parse('{"run_id":"r1","workflow":"consensus-genome","inputs":{"x":1}}')
        self.assertEqual(req.run_id, "r1")
        self.assertEqual(req.workflow, "consensus-genome")

    def test_rejects_bad_json(self):
        with self.assertRaises(InvalidRunRequest):
            RunRequest.parse("{not json")

    def test_rejects_traversal_in_workflow(self):
        with self.assertRaises(InvalidRunRequest):
            RunRequest.parse('{"run_id":"r1","workflow":"../etc","inputs":{}}')

    def test_rejects_bad_run_id(self):
        with self.assertRaises(InvalidRunRequest):
            RunRequest.parse('{"run_id":"a/b","workflow":"amr","inputs":{}}')

    def test_requires_inputs_object(self):
        with self.assertRaises(InvalidRunRequest):
            RunRequest.parse('{"run_id":"r1","workflow":"amr","inputs":[]}')


class TestWorkflowPath(unittest.TestCase):
    def test_confined_to_workflows_dir(self):
        cfg = _cfg(workflows_dir="/workflows")
        self.assertEqual(
            runner_mod.workflow_wdl_path(cfg, "amr"), "/workflows/amr/amr.wdl"
        )

    def test_command_targets_s3_output(self):
        cfg = _cfg()
        req = RunRequest(run_id="r1", workflow="amr", inputs={})
        cmd = runner_mod.build_miniwdl_command(cfg, req, "/tmp/in.json")
        self.assertEqual(cmd[0:2], ["miniwdl", "run"])
        self.assertIn("s3://b/runs/r1/outputs", cmd)


class TestProcessOne(unittest.TestCase):
    def test_success_records_status(self):
        cfg = _cfg()
        queue = mock.Mock()
        queue.claim.return_value = "processing/r1.json"
        queue.fetch.return_value = b'{"run_id":"r1","workflow":"amr","inputs":{}}'
        fake_proc = mock.Mock(return_value=mock.Mock(returncode=0, stderr=""))
        r = runner_mod.Runner(cfg, queue, run_subprocess=fake_proc)

        self.assertTrue(r.process_one("requests/r1.json"))
        states = [c.args[1]["state"] for c in queue.write_status.call_args_list]
        self.assertEqual(states, ["running", "succeeded"])

    def test_malformed_is_quarantined(self):
        cfg = _cfg()
        queue = mock.Mock()
        queue.claim.return_value = "processing/bad.json"
        queue.fetch.return_value = b"{not json"
        r = runner_mod.Runner(cfg, queue, run_subprocess=mock.Mock())

        self.assertTrue(r.process_one("requests/bad.json"))
        queue.quarantine.assert_called_once_with("processing/bad.json")

    def test_already_claimed_is_noop(self):
        cfg = _cfg()
        queue = mock.Mock()
        queue.claim.return_value = None
        r = runner_mod.Runner(cfg, queue, run_subprocess=mock.Mock())
        self.assertFalse(r.process_one("requests/r1.json"))


if __name__ == "__main__":
    unittest.main()
