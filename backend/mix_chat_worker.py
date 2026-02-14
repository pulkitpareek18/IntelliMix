from __future__ import annotations

import logging
import os
import time

from mix_chat_queue import pop_run
from mix_chat_runner import process_mix_chat_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger("mix_chat_worker")


def main() -> None:
    poll_seconds = max(1, int(os.environ.get("MIX_CHAT_WORKER_POLL_SECONDS", "5")))
    LOGGER.info("mix chat worker started (poll=%ss)", poll_seconds)
    while True:
        run_id = pop_run(block_seconds=poll_seconds)
        if not run_id:
            continue
        LOGGER.info("processing run %s", run_id)
        try:
            process_mix_chat_run(run_id)
        except Exception:
            LOGGER.exception("worker failed processing run %s", run_id)
            time.sleep(1)


if __name__ == "__main__":
    main()
