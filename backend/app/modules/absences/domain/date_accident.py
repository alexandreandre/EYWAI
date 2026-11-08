"""Date de l'accident ou de la première constatation d'un arrêt (DSN 60.012).

Pas de colonne en base : la date est rangée sous la clé réservée
``date_accident`` de ``demi_journees``. Les arrêts n'y mettent jamais de
demi-journée, et les lecteurs du champ cherchent des jours ISO. Passer par ces
fonctions : elles seules connaissent cette clé.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Mapping, Optional

CLE_DATE_ACCIDENT = "date_accident"
#: Arrêts qui portent une date d'accident (motifs DSN 04, 05 et 06).
TYPES_ARRET_ACCIDENT = ("arret_at", "arret_maladie_pro")


def date_accident_de(absence: Mapping[str, Any]) -> Optional[date]:
    """La date saisie sur la demande d'absence, sinon None."""
    demi = absence.get("demi_journees")
    if not isinstance(demi, dict):
        return None
    try:
        return date.fromisoformat(str(demi.get(CLE_DATE_ACCIDENT) or "")[:10])
    except ValueError:
        return None


def avec_date_accident(demi_journees: Any, jour: Optional[date]) -> Dict[str, Any]:
    """Le champ ``demi_journees`` avec la date posée (ou retirée si None)."""
    resultat = dict(demi_journees) if isinstance(demi_journees, dict) else {}
    if jour is None:
        resultat.pop(CLE_DATE_ACCIDENT, None)
    else:
        resultat[CLE_DATE_ACCIDENT] = jour.isoformat()
    return resultat


def refus_date_accident(type_absence: str, jour: date, premier_jour: Optional[date]) -> Optional[str]:
    """Pourquoi cette date ne peut pas être enregistrée, en français simple."""
    if type_absence not in TYPES_ARRET_ACCIDENT:
        return (
            "La date de l'accident ne concerne qu'un accident du travail, de trajet "
            "ou une maladie professionnelle : retirez-la pour cet arrêt."
        )
    if premier_jour and jour > premier_jour:
        return (
            "La date de l'accident ne peut pas être après le premier jour d'arrêt "
            f"({premier_jour:%d/%m/%Y}) : corrigez l'une des deux dates."
        )
    return None
