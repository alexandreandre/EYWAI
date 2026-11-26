"""Un arrêt saisi ne recouvre pas un arrêt déjà enregistré.

Un même jour ne porte qu'un arrêt : deux arrêts sur les mêmes jours
doubleraient le maintien, les IJ et les signalements DSN. La saisie RH est
refusée avec les dates de l'arrêt existant et, quand la nouvelle période va
au-delà, le jour où commence la prolongation (cas du 26/11 : arrêt importé de
la DSN jusqu'au 30/06, ressaisi du 01/05 au 27/11).

L'import DSN garde sa propre règle (il ne crée que les jours manquants).

Module pur.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Mapping, Optional

from app.modules.absences.domain.enums import IJSS_ELIGIBLE_TYPES
from app.modules.absences.domain.nature_arret import LIBELLES_NATURE

STATUTS_QUI_COMPTENT = frozenset({"validated", "pending"})


def _jour(valeur: object) -> date:
    return valeur if isinstance(valeur, date) else date.fromisoformat(str(valeur)[:10])


def _fr(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def refus_chevauchement_arret(
    nature: Optional[str],
    jours: Iterable[object],
    absences_existantes: Iterable[Mapping[str, object]],
) -> Optional[str]:
    """La phrase de refus si `jours` recouvre un arrêt validé ou en attente, sinon None."""
    if nature not in IJSS_ELIGIBLE_TYPES:
        return None
    nouveaux = {_jour(j) for j in jours}
    if not nouveaux:
        return None
    for absence in absences_existantes:
        if absence.get("type") not in IJSS_ELIGIBLE_TYPES:
            continue
        if absence.get("status") not in STATUTS_QUI_COMPTENT:
            continue
        existants = {_jour(j) for j in (absence.get("selected_days") or [])}
        if not existants & nouveaux:
            continue
        debut, fin = min(existants), max(existants)
        libelle = LIBELLES_NATURE.get(str(absence.get("type")), "arrêt").lower()
        phrase = (
            f"Ce salarié a déjà un {libelle} enregistré du {_fr(debut)} au {_fr(fin)}, "
            "qui recouvre la période saisie."
        )
        if max(nouveaux) > fin:
            phrase += (
                f" Pour une prolongation, saisissez la période à partir du "
                f"{_fr(fin + timedelta(days=1))}."
            )
        else:
            phrase += " Pour le modifier, annulez-le puis saisissez la bonne période."
        return phrase
    return None
