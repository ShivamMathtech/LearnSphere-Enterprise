"""Single process scheduler with a heartbeat. Email claim transitions support retries."""

import json
import logging
from pathlib import Path
import signal
import sys
import threading
import time
from app.tasks.worker import run_once

HEARTBEAT = Path("/tmp/learnsphere-worker-heartbeat") if sys.platform != "win32" else Path("data/worker-heartbeat")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if "--health" in sys.argv:
        raise SystemExit(0 if HEARTBEAT.exists() and time.time() - HEARTBEAT.stat().st_mtime < 180 else 1)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            result = run_once()
            HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
            HEARTBEAT.touch()
            logging.info(json.dumps({"event": "worker_cycle", **result}))
        except Exception as exc:
            logging.error(json.dumps({"event": "worker_failure", "error_type": type(exc).__name__}))
        stop.wait(60)


if __name__ == "__main__":
    main()
