"""Fige les entrées nécessaires au diff de conformité DSN.

Le dépôt est public : les entrées contiennent l'état civil et la paie de
salariés réels, elles ne peuvent donc pas y vivre. Ce script les capture sous
``data/_dsn_conformance/<societe>/<mois>/`` (gitignoré comme tout ``data/``),
avec la DSN du cabinet du même mois comme référence.

Usage :
    python scripts/dsn_conformance_snapshot.py                  # tout ce qui existe
    python scripts/dsn_conformance_snapshot.py --societe colorplast --mois 2026-05
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.exports.infrastructure.export_dsn import (  # noqa: E402
    get_company_data,
    get_dsn_employees_data,
)

RACINE = Path(__file__).resolve().parents[2]
SORTIE = RACINE / "data" / "_dsn_conformance"

# Dossier de données -> nom exact en base.
SOCIETES: Dict[str, str] = {
    "cartol": "Cartol Industrie",
    "colorplast": "Colorplast",
    "comitech": "Comitech Composite",
    "lewis": "LEWIS",
    "maji": "MAJI",
    "mbc": "Mont Blanc Composite",
    "zone": "Zone 404 Mars",
}


def id_societe(nom: str) -> Optional[str]:
    reponse = (
        supabase.table("companies").select("id,company_name").eq("company_name", nom).execute()
    )
    lignes = reponse.data or []
    return lignes[0]["id"] if lignes else None


def charger_settings(company_id: str, dossier: str) -> Optional[Dict]:
    """Paramétrage DSN de la société : la base d'abord, le fichier de reprise sinon.

    Tant que ``company_dsn_settings`` n'est pas déployée, on retombe sur le
    fichier produit par ``dsn_settings_reprise.py --fichier``.
    """
    from app.modules.dsn_export.domain.settings import vers_dict
    from app.modules.dsn_export.infrastructure import settings_repository

    settings = settings_repository.charger(company_id)
    if settings.est_complet():
        return vers_dict(settings)

    hors_ligne = SORTIE / dossier / "settings.json"
    if hors_ligne.exists():
        return json.loads(hors_ligne.read_text())
    return None


def capturer(dossier: str, mois: str) -> bool:
    reference = RACINE / "data" / dossier / "dsn" / f"{mois}.dsn"
    if not reference.exists():
        print(f"  {dossier} {mois} : pas de DSN cabinet, ignoré")
        return False

    company_id = id_societe(SOCIETES[dossier])
    if not company_id:
        print(f"  {dossier} : société introuvable en base")
        return False

    company = get_company_data(company_id)
    employees, totaux = get_dsn_employees_data(company_id, mois)
    if not employees:
        print(f"  {dossier} {mois} : aucun bulletin en base, ignoré")
        return False
    settings = charger_settings(company_id, dossier)

    cible = SORTIE / dossier / mois
    cible.mkdir(parents=True, exist_ok=True)
    (cible / "input.json").write_text(
        json.dumps(
            {
                "societe": dossier,
                "company_name": SOCIETES[dossier],
                "periode": mois,
                "company": company,
                "employees_data": employees,
                "totaux": totaux,
                "dsn_settings": settings,
            },
            ensure_ascii=False,
            default=str,
        )
    )
    (cible / "reference.dsn").write_bytes(reference.read_bytes())
    print(f"  {dossier} {mois} : {len(employees)} salariés figés")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--societe", choices=sorted(SOCIETES), help="dossier de données")
    parser.add_argument("--mois", help="période AAAA-MM")
    args = parser.parse_args()

    dossiers = [args.societe] if args.societe else sorted(SOCIETES)
    total = 0
    for dossier in dossiers:
        repertoire = RACINE / "data" / dossier / "dsn"
        if not repertoire.exists():
            continue
        mois_dispos = (
            [args.mois]
            if args.mois
            else sorted(f.stem for f in repertoire.glob("*.dsn"))
        )
        print(f"{dossier} :")
        for mois in mois_dispos:
            if capturer(dossier, mois):
                total += 1
    print(f"\n{total} instantané(s) écrits sous {SORTIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
