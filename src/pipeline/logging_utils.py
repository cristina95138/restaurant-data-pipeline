"""Structured JSON logging.

Cloud Run ships stdout to Cloud Logging, which parses JSON lines and honours the
``severity`` field. Log-based metrics on ``event`` + ``severity`` drive the
alert policies described in deploy/README.md.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


def log(event: str, severity: str = "INFO", **fields: Any) -> None:
    record = {
        "severity": severity,
        "event": event,
        "time": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    print(json.dumps(record, default=str), file=sys.stdout, flush=True)
