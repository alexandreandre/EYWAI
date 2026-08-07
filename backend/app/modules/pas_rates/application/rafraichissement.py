"""Rafraîchir le taux PAS d'un salarié dont la fiche n'est pas réécrite.

L'import DSN classe un salarié déjà connu en « ignorer » : sa fiche n'est pas
réécrite, pour ne pas effacer les corrections faites à la main par les RH. Cette
protection vaut pour le salaire ou le contrat, qui se décident en interne. Elle
n'a pas de sens pour le taux de prélèvement à la source, qui ne peut venir que
de la DGFiP et change tous les mois.

Ce module extrait le seul taux du payload d'import et l'écrit s'il diffère,
avec sa période d'origine. Rien d'autre de la fiche n'est touché.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.logging import get_logger
from app.modules.pas_rates.infrastructure import repository as repo

logger = get_logger("modules.pas_rates.rafraichissement")


def _bloc_pas(payload: Dict[str, Any]) -> Dict[str, Any]:
    specificites = payload.get("specificites_paie")
    if not isinstance(specificites, dict):
        return {}
    bloc = specificites.get("prelevement_a_la_source")
    return bloc if isinstance(bloc, dict) else {}


def _taux(valeur: Any) -> Optional[float]:
    if valeur is None or valeur == "":
        return None
    try:
        return round(float(valeur), 2)
    except (TypeError, ValueError):
        return None


def rafraichir_depuis_import(
    company_id: str,
    employee_row: Dict[str, Any],
    payload: Dict[str, Any],
    periode: Optional[str],
    source_fichier: str = "",
    applied_by: Optional[str] = None,
) -> bool:
    """Écrit le taux du fichier s'il diffère de celui en base. Renvoie True si écrit.

    Sans période, on ne peut pas dater le taux : on s'abstient plutôt que de
    poser une valeur dont personne ne saura d'où elle vient.
    """
    if not periode:
        return False

    bloc_fichier = _bloc_pas(payload)
    taux_fichier = _taux(bloc_fichier.get("taux"))
    if taux_fichier is None:
        return False

    employee_id = str(employee_row.get("id") or "")
    if not employee_id:
        return False

    bloc_actuel = _bloc_pas(employee_row)
    taux_actuel = _taux(bloc_actuel.get("taux"))
    type_fichier = bloc_fichier.get("type_taux") or None
    type_actuel = bloc_actuel.get("type_taux") or None
    periode_actuelle = bloc_actuel.get("periode") or None

    inchange = (
        taux_actuel == taux_fichier
        and type_actuel == type_fichier
        and periode_actuelle == periode
    )
    if inchange:
        return False

    # Une DSN plus ancienne que le taux détenu ne doit pas le faire reculer :
    # les mois d'un même lot ne sont pas toujours importés dans l'ordre.
    if periode_actuelle and periode_actuelle > periode:
        return False

    repo.enregistrer_taux(
        [
            {
                "company_id": company_id,
                "employee_id": employee_id,
                "periode": periode,
                "taux": taux_fichier,
                "type_taux": type_fichier,
                "identifiant_taux": bloc_fichier.get("identifiant_taux") or None,
                "source": "dsn",
                "source_fichier": source_fichier or None,
                "applied_by": applied_by,
            }
        ]
    )
    repo.maj_taux_courant(
        employee_id,
        taux_fichier,
        type_fichier,
        bloc_fichier.get("identifiant_taux") or None,
        periode,
    )
    logger.info(
        "Taux PAS rafraîchi à l'import pour %s : %s -> %s (%s)",
        employee_id,
        taux_actuel,
        taux_fichier,
        periode,
    )
    return True
