#!/usr/bin/env python3
"""
Paramétrage badgeuse d'une société à horaires variables.

Deux réglages, aucune donnée touchée (cf.
`docs/superpowers/specs/2026-08-04-badgeuse-colorplast-design.md` § 4.2) :

1. comptabilisation des pointages activée, avec une pause déduite et un seuil
   de présence en deçà duquel elle ne s'applique pas — Colorplast : 30 min
   au-delà de 6 h, rien sur une demi-journée ;
2. aucun créneau horaire, les horaires variant d'un jour à l'autre.

Ni gabarit de semaine, ni calendrier, ni heures réelles ne sont modifiés : le
seuil suffit à reproduire la règle. Le script est idempotent.

Usage (depuis backend/) :
    python scripts/setup_badgeuse_colorplast.py
    python scripts/setup_badgeuse_colorplast.py --apply --project-ref <ref>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

env_file = BACKEND_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from app.core.database import get_supabase_admin_client  # noqa: E402

DEFAULT_COMPANY = "Colorplast"

PUNCH_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    # Pause déjeuner de 30 min, ignorée en deçà de 6 h de présence : une
    # demi-journée n'en subit aucune, comme sur leurs feuilles papier.
    "default_break_deduct_minutes": 30,
    "break_threshold_minutes": 360,
    "tolerance_minutes": 30,
    "use_last_nonzero_exit": True,
    # Sans créneau, la détection ne sert pas ; on garde la valeur par défaut.
    "slot_detection": "shift_code",
    "within_tolerance_pay_theoretical": True,
    "require_manager_validation_for_overtime": True,
}


def project_ref_from_env() -> str:
    """Référence du projet Supabase visé, extraite de l'URL."""
    url = os.environ.get("SUPABASE_URL", "")
    host = url.split("//", 1)[-1].split("/", 1)[0]
    return host.split(".", 1)[0] if host else "(inconnu)"


def resolve_company(client, name: str) -> Dict[str, Any]:
    resp = (
        client.table("companies")
        .select("id, company_name")
        .eq("company_name", name)
        .execute()
    )
    rows = resp.data or []
    if len(rows) != 1:
        raise SystemExit(
            f"Société « {name} » : {len(rows)} correspondance(s), il en faut une."
        )
    return rows[0]


def settings_diff(current: Dict[str, Any] | None) -> List[str]:
    """Ce que le paramétrage changerait, réglage par réglage."""
    if current is None:
        return [f"{k} = {v}" for k, v in PUNCH_SETTINGS.items()]
    return [
        f"{k} : {current.get(k)!r} → {v!r}"
        for k, v in PUNCH_SETTINGS.items()
        if current.get(k) != v
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Paramètre la badgeuse d'une société à horaires variables"
    )
    parser.add_argument("--company", default=DEFAULT_COMPANY)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Écrit en base. Sans ce drapeau, simple aperçu.",
    )
    parser.add_argument(
        "--project-ref",
        help="Référence du projet Supabase attendue. Obligatoire avec --apply.",
    )
    args = parser.parse_args()

    ref = project_ref_from_env()
    print(f"Projet Supabase visé : {ref}")

    if args.apply:
        if not args.project_ref:
            raise SystemExit(
                "--apply exige --project-ref pour confirmer l'environnement visé."
            )
        if args.project_ref != ref:
            raise SystemExit(
                f"Projet attendu {args.project_ref}, projet connecté {ref}. Rien fait."
            )

    client = get_supabase_admin_client()
    company = resolve_company(client, args.company)
    company_id = str(company["id"])
    print(f"Société : {company['company_name']} ({company_id})\n")

    print("1. Comptabilisation des pointages")
    current = (
        client.table("company_punch_accounting_settings")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    ).data
    current_row = current[0] if current else None
    diff = settings_diff(current_row)
    if not diff:
        print("   déjà conforme")
    else:
        for line in diff:
            print(f"   - {line}")
        if args.apply:
            payload = dict(PUNCH_SETTINGS)
            payload["company_id"] = company_id
            client.table("company_punch_accounting_settings").upsert(
                payload, on_conflict="company_id"
            ).execute()

    print("\n2. Créneaux horaires")
    slots = (
        client.table("company_punch_shift_slots")
        .select("id, label")
        .eq("company_id", company_id)
        .execute()
    ).data or []
    if slots:
        print(f"   ⚠ {len(slots)} créneau(x) configuré(s) : leur pause prendra le")
        print("     pas sur la pause par défaut. À supprimer depuis l'interface.")
    else:
        print("   aucun, c'est ce qu'il faut")

    print("\n" + ("APPLIQUÉ" if args.apply else "APERÇU (aucune écriture)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
