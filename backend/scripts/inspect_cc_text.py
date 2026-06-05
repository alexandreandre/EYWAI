#!/usr/bin/env python3
"""Inspecte le texte KALI mis en cache pour une convention (diagnostic grille paie)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

MARKERS = (
    "minima hiérarchiques",
    "minima hierarchiques",
    "salaires minima hiérarchiques",
    "groupe d'emploi",
    "groupes d'emploi",
    "classe d'emploi",
    "classes d'emploi",
    "valeur du point",
    "valeur de point",
    "annexe 6",
    "barème unique",
    "bareme unique",
)

SMH_ROW_PATTERN = re.compile(
    r"(?i)\b([A-I])\b[\s|]+(\d{1,2})[\s|]+([\d\s]+(?:[,.]\d+)?)\s*(?:€|euros?)\b"
)


def _count_markers(text: str) -> dict[str, int]:
    lower = text.lower()
    return {m: lower.count(m.lower()) for m in MARKERS}


def _find_smh_windows(text: str, *, window: int = 400) -> list[dict]:
    windows: list[dict] = []
    for match in SMH_ROW_PATTERN.finditer(text):
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        windows.append(
            {
                "groupe": match.group(1),
                "classe": int(match.group(2)),
                "montant_raw": match.group(3).strip(),
                "excerpt": text[start:end].strip(),
            }
        )
    return windows


def inspect_text(text: str) -> dict:
    from app.modules.collective_agreements.rules.bareme_parser import parse_smh_national

    markers = _count_markers(text)
    smh_rows = _find_smh_windows(text)
    parsed = parse_smh_national(text)
    return {
        "character_count": len(text),
        "markers": markers,
        "smh_row_matches": len(smh_rows),
        "smh_sample_rows": smh_rows[:5],
        "parser_result": {
            "found": parsed is not None,
            "minima_count": len(parsed.minima) if parsed else 0,
            "zone_libelle": parsed.zone_libelle if parsed else None,
            "date_effet": parsed.date_effet if parsed else None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspecte le texte CC en cache")
    parser.add_argument("--idcc", help="IDCC (ex. 3248)")
    parser.add_argument("--agreement-id", help="UUID catalogue convention")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    args = parser.parse_args()

    if not args.idcc and not args.agreement_id:
        parser.error("Indiquer --idcc ou --agreement-id")

    from app.modules.collective_agreements.application.service import (
        get_collective_agreements_service,
    )
    from app.modules.collective_agreements.infrastructure.providers import (
        AgreementTextCacheProvider,
    )

    cache = AgreementTextCacheProvider()
    agreements = get_collective_agreements_service()

    agreement_id = args.agreement_id
    idcc = args.idcc
    if not agreement_id and idcc:
        items = agreements.list_catalog(idcc=idcc)
        if not items:
            print(f"Aucune convention catalogue pour IDCC {idcc}", file=sys.stderr)
            return 1
        agreement_id = items[0]["id"]
        idcc = items[0].get("idcc") or idcc

    text = cache.get_full_text(agreement_id or "")
    if not text:
        print(f"Texte cache absent pour agreement_id={agreement_id}", file=sys.stderr)
        return 1

    report = inspect_text(text)
    report["agreement_id"] = agreement_id
    report["idcc"] = idcc

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"IDCC {idcc} — agreement {agreement_id}")
        print(f"  Caractères : {report['character_count']:,}")
        print(f"  Lignes SMH détectées (regex) : {report['smh_row_matches']}")
        print(f"  Parser SMH : {report['parser_result']}")
        print("  Marqueurs :")
        for key, count in report["markers"].items():
            if count:
                print(f"    - {key}: {count}")
        if report["smh_sample_rows"]:
            print("\n  Exemples lignes SMH :")
            for row in report["smh_sample_rows"]:
                print(
                    f"    Groupe {row['groupe']} classe {row['classe']} "
                    f"→ {row['montant_raw']} €"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
