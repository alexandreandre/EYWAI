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

# Libellés divergents constatés en base, fusionnés vers une forme unique.
RENOMMAGES = {
    "Indemnite de transport": "Indemnité de transport",
    "Paniers Jours non soumis": "Paniers jours non soumis",
}


# En deçà, une quantité « constante » relève du hasard, pas d'une convention.
MIN_LIGNES_POUR_CONCLURE = 5


def est_concerne(name: str) -> bool:
    low = (name or "").lower()
    return "panier" in low or "repas" in low


def deduire_semantique(lignes: list[dict]) -> tuple[str, str]:
    """Déduit la sémantique de payroll_quantity depuis les données.

    Renvoie (kind, justification).

    Une liste en dur de libellés serait fragile : « Prime panier soumises »
    stocke 2,50 € en quantité, comme « Paniers Jours non soumis » stocke 7,50 €,
    et rien dans le libellé ne le dit. Deux signaux concordants font foi :
      - la quantité est CONSTANTE sur toutes les lignes du libellé ;
      - montant / quantité donne des entiers (c'est le nombre d'unités).
    """
    qtes = {float(l["payroll_quantity"]) for l in lignes if l.get("payroll_quantity")}
    if not qtes:
        return "count", "aucune quantité renseignée"
    if len(qtes) > 1:
        return "count", f"quantité variable ({len(qtes)} valeurs distinctes)"

    unique = next(iter(qtes))
    ratios = [
        float(l["amount"]) / unique
        for l in lignes
        if l.get("payroll_quantity") and l.get("amount")
    ]
    if not ratios:
        return "count", "aucun montant exploitable"
    if len(ratios) < MIN_LIGNES_POUR_CONCLURE:
        # Sur deux ou trois lignes, une quantité « constante » ne prouve rien.
        # On garde le comportement historique plutôt que de deviner.
        return "count", f"seulement {len(ratios)} ligne(s), trop peu pour conclure"
    entiers = sum(1 for r in ratios if abs(r - round(r)) < 0.01)
    if entiers == len(ratios):
        return (
            "unit_value",
            f"quantité constante à {unique} et montant/quantité toujours entier",
        )
    return "count", f"quantité constante à {unique} mais montants non multiples"


def lire_tout(colonnes: str) -> list[dict]:
    """Lit monthly_inputs en entier.

    PostgREST plafonne une requête à 1000 lignes sans le dire ; la table en
    compte près de 2900. Sans pagination, deux tiers des saisies passeraient
    silencieusement à travers la reprise.
    """
    taille, debut, tout = 1000, 0, []
    while True:
        lot = (
            supabase.table("monthly_inputs")
            .select(colonnes)
            .range(debut, debut + taille - 1)
            .execute()
            .data
            or []
        )
        tout.extend(lot)
        if len(lot) < taille:
            return tout
        debut += taille


def annoter(apply: bool) -> int:
    rows = lire_tout("id, company_id, name, payroll_quantity, amount, quantity_kind")

    # Groupé par (entreprise, libellé) et non par libellé seul : le renommage
    # fusionne « Paniers Jours non soumis » (Mont Blanc, valeur unitaire 7,50)
    # avec « Paniers jours non soumis » (Lewis, nombre de jours). Sur le libellé
    # seul, le groupe fusionné paraît « à quantité variable » et bascule à tort
    # en count, ce qui reperdrait la valeur unitaire des 206 lignes Mont Blanc.
    # L'entreprise reste discriminante après renommage : le script redevient
    # rejouable sans rien casser.
    par_libelle: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        nom = row.get("name") or ""
        if est_concerne(nom):
            par_libelle.setdefault((row.get("company_id") or "", nom), []).append(row)

    print(f"{len(rows)} saisies lues, {len(par_libelle)} groupe(s) panier/repas.\n")
    a_traiter: list[tuple[dict, str]] = []
    for (_, nom), lignes in sorted(par_libelle.items(), key=lambda kv: kv[0][::-1]):
        kind, pourquoi = deduire_semantique(lignes)
        manquantes = [l for l in lignes if l.get("quantity_kind") != kind]
        print(f"  {len(lignes):4} | {nom:30} -> {kind:10} ({pourquoi})")
        a_traiter.extend((l, kind) for l in manquantes)

    print(f"\n{len(a_traiter)} ligne(s) à annoter.")
    if not apply:
        return len(a_traiter)

    for row, attendu in a_traiter:
        supabase.table("monthly_inputs").update({"quantity_kind": attendu}).eq(
            "id", row["id"]
        ).execute()
    print(f"{len(a_traiter)} saisies annotées.")
    return len(a_traiter)


def normaliser_libelles(apply: bool) -> int:
    """Renomme les libellés divergents. Refuse tant que l'annotation manque."""
    rows = lire_tout("id, name, quantity_kind")
    cibles = [r for r in rows if r.get("name") in RENOMMAGES]
    non_annotees = [
        r
        for r in cibles
        if not r.get("quantity_kind") and "panier" in (r.get("name") or "").lower()
    ]

    print(f"\n{len(cibles)} libellé(s) à normaliser.")
    if not apply:
        # En simulation, l'annotation n'a rien écrit : il est normal que les
        # lignes ne soient pas encore annotées. On l'annonce sans abandonner.
        if non_annotees:
            print(
                f"  ({len(non_annotees)} attendent leur quantity_kind — "
                "l'exécution réelle les annotera d'abord)"
            )
        return len(cibles)

    if non_annotees:
        print(
            f"ABANDON : {len(non_annotees)} ligne(s) panier à renommer n'ont pas "
            "encore de quantity_kind. Annoter d'abord — après renommage, la "
            "sémantique ne serait plus déductible."
        )
        return -1

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
