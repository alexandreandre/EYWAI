"""Porte vers le paramétrage DSN ce que le versement trimestriel reprend du cabinet.

Pour Colorplast et Comitech, depuis la DSN Quadra de fin de trimestre la plus
récente (`data/<societe>/dsn/2026-06.dsn`) :

- ``versements[].jour_paiement`` : le jour de la date de paiement (20.011) de
  chaque organisme complémentaire, le 25 chez le cabinet ;
- ``organismes_complementaires[].type_population`` : le type de population
  (55.002) de chaque contrat, code de la fiche de l'organisme.

Les modalités de paiement « ne doivent pas être modifiées unilatéralement »
(FAQ DSN OC, net-entreprises) : on reprend celles du cabinet, rien d'autre.

SIMULATION PAR DÉFAUT ; ``--appliquer --projet <ref>`` écrit, et refuse si le
ref n'est pas celui du projet pointé par backend/.env.

    .venv/bin/python scripts/dsn_versements_trimestriels.py
    .venv/bin/python scripts/dsn_versements_trimestriels.py --appliquer --projet <ref>
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RACINE = Path(__file__).resolve().parents[2]
SOCIETES = {"colorplast": "Colorplast", "comitech": "Comitech Composite"}
MOIS_DE_REFERENCE = "2026-06"


def completer(
    versements: List[Dict[str, Any]],
    contrats: List[Dict[str, Any]],
    contenu: bytes,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Les versements et contrats complétés depuis la DSN du cabinet, et ce qui change."""
    from app.modules.dsn_export.domain.settings import _versements, types_de_population

    jours = {
        v["organisme"]: v["jour_paiement"] for v in _versements(contenu) if v.get("jour_paiement")
    }
    types = types_de_population(contenu)
    versements, contrats = copy.deepcopy(versements), copy.deepcopy(contrats)
    changements: List[str] = []
    for versement in versements:
        jour = jours.get(str(versement.get("organisme") or ""))
        if jour and versement.get("jour_paiement") != jour:
            changements.append(f"{versement['organisme']} : jour de paiement {jour}")
            versement["jour_paiement"] = jour
    for contrat in contrats:
        type_population = types.get(str(contrat.get("reference") or ""))
        if type_population and contrat.get("type_population") != type_population:
            changements.append(
                f"{contrat.get('organisme')} {contrat['reference']} : type de population "
                f"« {type_population} »"
            )
            contrat["type_population"] = type_population
    return versements, contrats, changements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--appliquer", action="store_true")
    parser.add_argument("--projet", default="")
    args = parser.parse_args()

    from app.core.database import supabase, supabase_url
    from app.modules.dsn_export.infrastructure import settings_repository

    projet = (supabase_url or "").split("//")[-1].split(".")[0]
    if args.appliquer and args.projet != projet:
        print(f"Refus : --projet {args.projet or '(vide)'} n'est pas le projet pointé ({projet}).")
        return 2

    for dossier, nom in SOCIETES.items():
        chemin = RACINE / "data" / dossier / "dsn" / f"{MOIS_DE_REFERENCE}.dsn"
        if not chemin.exists():
            print(f"{nom} : {chemin} absent, ignoré")
            continue
        lignes = supabase.table("companies").select("id").eq("company_name", nom).execute().data
        if not lignes:
            print(f"{nom} : société introuvable, ignorée")
            continue
        company_id = lignes[0]["id"]
        parametrage = settings_repository.charger(company_id)
        versements, contrats, changements = completer(
            parametrage.versements, parametrage.organismes_complementaires, chemin.read_bytes()
        )
        if not changements:
            print(f"{nom} : déjà à jour")
            continue
        print(f"{nom} : {len(changements)} changement(s)")
        for changement in changements:
            print(f"  - {changement}")
        if args.appliquer:
            parametrage.versements = versements
            parametrage.organismes_complementaires = contrats
            settings_repository.enregistrer(company_id, parametrage)
            print(f"{nom} : écrit")
    if not args.appliquer:
        print("Simulation : rien n'est écrit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
