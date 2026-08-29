# backend/scripts/eval_timesheet_native_vs_hybrid.py
"""Compare hybrid vs native sur un dossier de relevés réels.

Usage : cd backend && ./venv/bin/python scripts/eval_timesheet_native_vs_hybrid.py <dossier>
Nécessite OPENROUTER_API_KEY (backend/.env). N'écrit rien en base (skip_audit).
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.modules.schedules.application import ai_fill  # noqa: E402


def _run(mode: str, path: Path, year: int, month: int):
    os.environ["TIMESHEET_EXTRACT_MODE"] = mode
    started = time.monotonic()
    try:
        resp = ai_fill.extract_timesheet(
            year=year,
            month=month,
            file_content=path.read_bytes(),
            filename=path.name,
            roster=[],
            skip_audit=True,
        )
        days = sum(len(e.days) for e in resp.employees)
        return {
            "durée_s": round(time.monotonic() - started, 1),
            "salariés": len(resp.employees),
            "jours": days,
            "méthode": resp.extraction_method,
            "avertissements": len(resp.warnings or []),
        }
    except Exception as exc:  # noqa: BLE001 - rapport d'éval
        return {"durée_s": round(time.monotonic() - started, 1), "erreur": str(exc)[:120]}


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    folder = Path(sys.argv[1])
    year = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    month = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    files = sorted(
        p for p in folder.iterdir()
        if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg")
    )
    for path in files:
        print(f"\n=== {path.name} ===")
        for mode in ("hybrid", "native"):
            print(f"  {mode:8s} {_run(mode, path, year, month)}")


if __name__ == "__main__":
    main()
