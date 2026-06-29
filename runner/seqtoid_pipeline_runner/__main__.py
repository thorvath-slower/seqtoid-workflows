"""CZID-72 — entry point (console script `seqtoid-pipeline-runner`): poll the S3 queue, dispatch,
shut down cleanly on SIGTERM (so Kubernetes rolling updates don't kill an in-flight claim)."""
from __future__ import annotations

import logging
import signal
import sys
import time

from .config import Config
from .queue import S3RequestQueue, make_s3_client
from .runner import Runner

log = logging.getLogger("seqtoid_pipeline_runner")


class _Shutdown:
    stop = False

    def __call__(self, *_a):
        self.stop = True


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = Config.from_env()
    queue = S3RequestQueue(make_s3_client(cfg), cfg)
    runner = Runner(cfg, queue)

    shutdown = _Shutdown()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("runner started: bucket=%s endpoint=%s poll=%ss", cfg.bucket, cfg.s3_endpoint, cfg.poll_interval_sec)
    while not shutdown.stop:
        try:
            pending = queue.list_pending()
            did_work = False
            for key in pending:
                if shutdown.stop:
                    break
                did_work = runner.process_one(key) or did_work
        except Exception:  # noqa: BLE001 — one bad iteration must not crash the loop
            log.exception("poll iteration failed; backing off")
            did_work = False
        if not did_work:
            for _ in range(cfg.poll_interval_sec):
                if shutdown.stop:
                    break
                time.sleep(1)
    log.info("runner stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
