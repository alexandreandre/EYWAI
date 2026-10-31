#!/usr/bin/env python3
"""Prévient les salariés dont le bulletin validé leur est remis aujourd'hui (D5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main() -> int:
    from app.core.database import supabase
    from app.modules.payslips.application.remise import notifier_bulletins_remis

    societes = (
        supabase.table("companies").select("id, company_name").eq("is_active", True).execute()
    ).data or []
    resultats = []
    echecs = 0
    for societe in societes:
        bilan = notifier_bulletins_remis(str(societe["id"]))
        echecs += bilan["echecs"]
        if bilan["notifies"] or bilan["echecs"]:
            resultats.append({"societe": societe.get("company_name"), **bilan})
    print(json.dumps({"societes": len(societes), "resultats": resultats}, ensure_ascii=False, indent=2))
    return 0 if echecs == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
