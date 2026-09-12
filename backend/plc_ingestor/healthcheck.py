from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


HEALTH_FILE = Path(os.getenv("PLC_HEALTH_FILE", "/tmp/plc-ingestor-health.json"))
STALE_AFTER_SECONDS = float(os.getenv("PLC_HEALTH_STALE_AFTER_SECONDS", "15"))


def main() -> int:
    try:
        payload = json.loads(HEALTH_FILE.read_text(encoding="utf-8"))
        if payload.get("state") != "live":
            return 1

        raw_last_success = payload.get("last_success_at")
        if not raw_last_success:
            return 1

        last_success = datetime.fromisoformat(raw_last_success)
        if last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=timezone.utc)

        age_seconds = (datetime.now(timezone.utc) - last_success.astimezone(timezone.utc)).total_seconds()
        return 0 if age_seconds <= STALE_AFTER_SECONDS else 1
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
