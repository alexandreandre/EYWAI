"""
Qui ne peut pas être contacté — inventaire des adresses e-mail manquantes.

Un salarié dont l'adresse est vide ou fabriquée à l'import DSN ne peut recevoir
ni lien d'activation, ni bulletin, ni relance : le compte existe, la boîte
n'existe pas. Ce script produit, société par société, la liste nominative des
fiches à compléter, pour la remettre au service RH.

    python -m scripts.adresses_manquantes            # tableau de couverture
    python -m scripts.adresses_manquantes --fichiers # + un .xlsx par société

LECTURE SEULE. Les fichiers atterrissent sous `data/_audits/adresses/`,
gitignoré : ils sont nominatifs.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List

from app.core.database import supabase
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email

RACINE = Path(__file__).resolve().parents[2] / "data" / "_audits" / "adresses"

COLONNES = [
    "Matricule",
    "Nom",
    "Prénom",
    "Date d'entrée",
    "Adresse enregistrée",
    "Motif",
    "Adresse à renseigner",
]


def _toutes_les_fiches() -> List[Dict]:
    """Toutes les fiches actives — paginé : PostgREST plafonne à 1000 lignes."""
    fiches: List[Dict] = []
    decalage = 0
    while True:
        lot = (
            supabase.table("employees")
            .select(
                "id, matricule, first_name, last_name, email, hire_date, "
                "company_id, employment_status"
            )
            .eq("employment_status", "actif")
            .range(decalage, decalage + 999)
            .execute()
        ).data or []
        fiches.extend(lot)
        if len(lot) < 1000:
            return fiches
        decalage += 1000


def _motif(email: str | None) -> str | None:
    """Pourquoi cette fiche n'est pas joignable, ou None si elle l'est."""
    valeur = (email or "").strip()
    if not valeur:
        return "aucune adresse"
    if is_dsn_import_placeholder_email(valeur):
        return "adresse fabriquée à l'import DSN"
    return None


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        "--fichiers",
        action="store_true",
        help="écrire un classeur par société sous data/_audits/adresses/",
    )
    options = parseur.parse_args()

    societes = {
        c["id"]: c["company_name"]
        for c in (supabase.table("companies").select("id, company_name").execute().data or [])
    }
    fiches = _toutes_les_fiches()

    manquantes: Dict[str, List[Dict]] = {}
    for fiche in fiches:
        motif = _motif(fiche.get("email"))
        if motif:
            manquantes.setdefault(fiche["company_id"], []).append({**fiche, "_motif": motif})

    print(f"\n{'Société':<22}{'Actifs':>8}{'Joignables':>12}{'À compléter':>13}")
    print("=" * 55)
    total_actifs = total_manquants = 0
    for cid, nom in sorted(societes.items(), key=lambda x: x[1] or ""):
        actifs = [f for f in fiches if f["company_id"] == cid]
        if not actifs:
            continue
        absents = manquantes.get(cid, [])
        total_actifs += len(actifs)
        total_manquants += len(absents)
        print(
            f"{nom:<22}{len(actifs):>8}{len(actifs) - len(absents):>12}{len(absents):>13}"
        )
    print("=" * 55)
    print(
        f"{'TOTAL':<22}{total_actifs:>8}"
        f"{total_actifs - total_manquants:>12}{total_manquants:>13}\n"
    )

    if not options.fichiers:
        return 0

    from app.shared.utils.export import generate_xlsx

    RACINE.mkdir(parents=True, exist_ok=True)
    horodatage = date.today().isoformat()
    for cid, absents in manquantes.items():
        nom = societes.get(cid, cid)
        lignes = [
            {
                "Matricule": f.get("matricule") or "",
                "Nom": f.get("last_name") or "",
                "Prénom": f.get("first_name") or "",
                "Date d'entrée": f.get("hire_date") or "",
                "Adresse enregistrée": (f.get("email") or "").strip(),
                "Motif": f["_motif"],
                "Adresse à renseigner": "",
            }
            for f in sorted(
                absents, key=lambda f: (f.get("last_name") or "", f.get("first_name") or "")
            )
        ]
        pente = "".join(ch if ch.isalnum() else "-" for ch in nom.lower()).strip("-")
        cible = RACINE / f"{horodatage}-adresses-a-completer-{pente}.xlsx"
        cible.write_bytes(generate_xlsx(lignes, COLONNES))
        print(f"  {cible.name}  ({len(lignes)} fiches)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
