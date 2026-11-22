"""A simple run log.

Every stage opens a RunLog. It prints messages to the screen, writes them to a
log file in logs/, and keeps counts (processed, skipped, failed, retried, ...).
At the end the counts are written as a summary.
"""

import datetime as dt
import json
from collections import Counter
from pathlib import Path


class RunLog:
    def __init__(self, stage: str, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        self.stage = stage
        self.started = dt.datetime.now()
        stamp = self.started.strftime("%Y%m%d-%H%M%S")
        self.path = log_dir / f"{stage}-{stamp}.log"
        self.counts: Counter = Counter()
        self._file = open(self.path, "w", encoding="utf-8")
        self.info(f"stage '{stage}' started")

    def info(self, message: str) -> None:
        line = f"{dt.datetime.now():%H:%M:%S} {message}"
        print(line, flush=True)
        self._file.write(line + "\n")
        self._file.flush()

    def count(self, what: str, n: int = 1) -> None:
        self.counts[what] += n

    def close(self) -> dict:
        summary = {
            "stage": self.stage,
            "started": self.started.isoformat(timespec="seconds"),
            "finished": dt.datetime.now().isoformat(timespec="seconds"),
            "counts": dict(self.counts),
        }
        self.info("summary: " + json.dumps(summary["counts"], ensure_ascii=False))
        self._file.close()
        return summary
