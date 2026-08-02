"""Annote la sémantique de payroll_quantity et normalise les libellés divergents.

payroll_quantity porte deux conventions inverses selon le libellé :
  - « Paniers Jours non soumis » (J majuscule, Mont Blanc Composite) stocke la
    VALEUR unitaire (7,5) ;
  - tous les autres libellés panier/repas stockent le NOMBRE d'unités.

Ce script ne touche à aucun montant : il renseigne quantity_kind, puis
normalise les libellés. L'ordre n'est pas négociable — le libellé est le seul
discriminant de la sémantique, le normaliser d'abord la détruirait.

Usage :
    python scripts/normalize_panier_quantities.py            # simulation
    python scripts/normalize_panier_quantities.py --apply    # écriture
"""

from __future__ import annotations

import argparse
import sys

from app.core.database import supabase

# Libellés dont payroll_quantity porte la valeur unitaire et non un nombre.
LIBELLES_VALEUR_UNITAIRE = {"Paniers Jours non soumis"}

# Libellés divergents constatés en base, fusionnés vers une forme unique.
RENOMMAGES = {
    "Indemnite de transport": "Indemnité de transport",
    "Paniers Jours non soumis": "Paniers jours non soumis",
}


def classer(name: str) -> str | None:
    """Renvoie 'unit_value', 'count', ou None si la ligne n'est pas concernée."""
    if name in LIBELLES_VALEUR_UNITAIRE:
        return "unit_value"
    low = (name or "").lower()
    if "panier" in low or "repas" in low:
        return "count"
    return None


def annoter(apply: bool) -> int:
    rows = (
        supabase.table("monthly_inputs")
        .select("id, name, payroll_quantity, amount, quantity_kind")
        .execute()
        .data
        or []
    )
    a_traiter = []
    for row in rows:
        attendu = classer(row.get("name") or "")
        if attendu is None or row.get("quantity_kind") == attendu:
            continue
        a_traiter.append((row, attendu))

    par_kind: dict[str, int] = {}
    for _, attendu in a_traiter:
        par_kind[attendu] = par_kind.get(attendu, 0) + 1
    print(f"{len(rows)} saisies lues, {len(a_traiter)} à annoter.")
    for kind, n in sorted(par_kind.items()):
        print(f"  {kind}: {n}")

    if not apply:
        for row, attendu in a_traiter[:10]:
            print(f'  "{row["name"]}" qty={row.get("payroll_quantity")} -> {attendu}')
        return len(a_traiter)

    for row, attendu in a_traiter:
        supabase.table("monthly_inputs").update({"quantity_kind": attendu}).eq(
            "id", row["id"]
        ).execute()
    print(f"{len(a_traiter)} saisies annotées.")
    return len(a_traiter)


def normaliser_libelles(apply: bool) -> int:
    """Renomme les libellés divergents. Refuse tant que l'annotation manque."""
    rows = (
        supabase.table("monthly_inputs")
        .select("id, name, quantity_kind")
        .execute()
        .data
        or []
    )
    cibles = [r for r in rows if r.get("name") in RENOMMAGES]
    non_annotees = [
        r
        for r in cibles
        if not r.get("quantity_kind") and "panier" in (r.get("name") or "").lower()
    ]
    if non_annotees:
        print(
            f"ABANDON : {len(non_annotees)} ligne(s) panier à renommer n'ont pas "
            "encore de quantity_kind. Annoter d'abord — le libellé est le seul "
            "discriminant de la sémantique."
        )
        return -1

    print(f"{len(cibles)} libellé(s) à normaliser.")
    if not apply:
        return len(cibles)

    for row in cibles:
        supabase.table("monthly_inputs").update({"name": RENOMMAGES[row["name"]]}).eq(
            "id", row["id"]
        ).execute()
    print(f"{len(cibles)} libellé(s) normalisé(s).")
    return len(cibles)


def _verifier_migration() -> bool:
    """La colonne quantity_kind doit exister avant toute chose."""
    try:
        supabase.table("monthly_inputs").select("quantity_kind").limit(1).execute()
        return True
    except Exception as exc:
        if "quantity_kind" in str(exc):
            print(
                "ABANDON : la colonne monthly_inputs.quantity_kind n'existe pas.\n"
                "Appliquer d'abord la migration "
                "20260803090000_monthly_inputs_quantity_kind.sql."
            )
            return False
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="écrit en base")
    args = parser.parse_args()

    if not _verifier_migration():
        return 1

    annoter(args.apply)
    if normaliser_libelles(args.apply) < 0:
        return 1
    if not args.apply:
        print("\nSimulation — relancer avec --apply pour écrire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
