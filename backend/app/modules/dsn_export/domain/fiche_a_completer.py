"""Ce que la fiche d'un salarié doit porter pour que sa DSN passe DSN-VAL.

Le constructeur de DSN n'invente jamais une valeur : une rubrique sans source
reste absente du fichier, et DSN-VAL refuse. Ces contrôles le disent avant,
sur la fiche, avec la rubrique en cause (CST-03, CCH-11, CCH-12, SIG-11).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

_PCS_ESE = re.compile(r"^\d{3}[a-z]$")
_DISPOSITIFS_APPRENTISSAGE = {"64", "65", "66", "81"}


def _dict(valeur: Any) -> Dict[str, Any]:
    return valeur if isinstance(valeur, dict) else {}


def fiche_a_completer(employee: Dict[str, Any]) -> List[str]:
    """Les manques de la fiche, un message par rubrique, sans nom de salarié."""
    classification = _dict(employee.get("classification_conventionnelle"))
    specs = _dict(employee.get("specificites_paie"))
    reprise = _dict(employee.get("dsn_reprise") or specs.get("dsn_reprise"))
    type_contrat = str(employee.get("contract_type") or "")
    apprenti = "apprenti" in type_contrat.lower() or (
        str(classification.get("dispositif_politique_publique") or "")
        in _DISPOSITIFS_APPRENTISSAGE
    )
    cdd = type_contrat.upper() == "CDD"
    manques: List[str] = []

    pcs = str(classification.get("pcs") or employee.get("pcs") or "").strip()
    if not pcs:
        manques.append(
            "Code PCS-ESE (S21.G00.40.004) manquant : rubrique obligatoire, "
            "à saisir sur la fiche (classification)"
        )
    elif not _PCS_ESE.match(pcs):
        manques.append(
            f"Code PCS-ESE (S21.G00.40.004) « {pcs} » hors format "
            "(trois chiffres et une lettre) : à vérifier sur la fiche"
        )

    if cdd or apprenti:
        fin = (
            employee.get("contract_end_date")
            or employee.get("date_fin_contrat")
            or reprise.get("date_fin_contrat")
        )
        if not fin:
            manques.append(
                "Date de fin prévisionnelle (S21.G00.40.010) manquante : "
                "obligatoire pour un CDD ou un contrat d'apprentissage à terme"
            )
    if apprenti and not (
        employee.get("niveau_diplome_prepare") or reprise.get("niveau_diplome_prepare")
    ):
        manques.append(
            "Niveau de diplôme préparé (S21.G00.30.025) manquant : "
            "obligatoire en apprentissage"
        )
    if cdd and not (
        classification.get("motif_recours")
        or employee.get("motif_recours_cdd")
        or reprise.get("motif_recours")
    ):
        manques.append(
            "Motif de recours au CDD (S21.G00.40.021) manquant : attendu par DSN-VAL"
        )
    return manques
