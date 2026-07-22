"""Vérifie l'état de l'import participation 2025 (lecture seule).

Usage (depuis backend/) :
    DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib" .venv-ci/bin/python \
        scripts/verify_participation_import_2025.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")

from app.core.database import supabase  # noqa: E402

COMPANY_NAMES = [
    "Mont Blanc Composite",
    "Cartol Industrie",
    "LEWIS",
    "Comitech Composite",
    "Colorplast",
]


def main() -> None:
    companies = (
        supabase.table("companies")
        .select("id, company_name")
        .in_("company_name", COMPANY_NAMES)
        .execute()
        .data
        or []
    )
    company_ids = [c["id"] for c in companies]
    cmap = {c["id"]: c["company_name"] for c in companies}

    campaigns = (
        supabase.table("participation_campaigns")
        .select("id, company_id, year, status")
        .in_("company_id", company_ids)
        .eq("year", 2025)
        .execute()
        .data
        or []
    )
    print(f"Campagnes 2025 : {len(campaigns)} (attendu 5, toutes status=closed)")
    for c in campaigns:
        print(f"  {cmap.get(c['company_id'])}: status={c['status']}")

    total_bulletins = 0
    for c in campaigns:
        bulletins = (
            supabase.table("participation_bulletins")
            .select("id, choice_type, status")
            .eq("campaign_id", c["id"])
            .execute()
            .data
            or []
        )
        total_bulletins += len(bulletins)
        non_responded = [b for b in bulletins if b["status"] != "responded"]
        if non_responded:
            print(f"  ANOMALIE {cmap.get(c['company_id'])}: {len(non_responded)} bulletin(s) non 'responded'")
    print(f"Total bulletins : {total_bulletins} (attendu 186)")

    linked = (
        supabase.table("monthly_inputs")
        .select("id", count="exact")
        .in_("company_id", company_ids)
        .not_.is_("participation_campaign_id", "null")
        .execute()
    )
    print(f"Saisies rattachées : {linked.count}")

    # Vérification ciblée : le montant GIRERD (PEE) doit être strictement
    # inchangé après l'import (aucune régénération de paie).
    girerd = (
        supabase.table("monthly_inputs")
        .select("amount, name")
        .in_("company_id", company_ids)
        .ilike("name", "%PEE%")
        .eq("amount", 5331.56)
        .execute()
        .data
        or []
    )
    print(f"Ligne GIRERD PEE 5331.56 toujours intacte : {'OUI' if girerd else 'NON — ALERTE'}")


if __name__ == "__main__":
    main()
