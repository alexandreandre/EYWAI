#!/usr/bin/env python3
"""Exécute les exports planifiés compta/banque dont next_run_at est dépassé."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    from app.modules.exports.application.scheduled_exports import (
        run_due_channel_schedules,
    )

    results = run_due_channel_schedules()
    summary = {
        "executed": len(results),
        "success": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
