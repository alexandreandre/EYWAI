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

# Seuls les arrêts validés comptent : un arrêt resté « en attente » (validation
# automatique interrompue) n'est visible nulle part et ne doit pas bloquer.
STATUTS_QUI_COMPTENT = frozenset({"validated"})


def _jour(valeur: object) -> date:
    return valeur if isinstance(valeur, date) else date.fromisoformat(str(valeur)[:10])


def _fr(jour: date) -> str:
    return jour.strftime("%d/%m/%Y")


def _blocs(jours: set[date]) -> list[tuple[date, date]]:
    """Les jours regroupés en périodes continues (un arrêt importé de la DSN
    est découpé en plusieurs lignes qui se suivent)."""
    blocs: list[tuple[date, date]] = []
    for jour in sorted(jours):
        if blocs and jour - blocs[-1][1] <= timedelta(days=1):
            blocs[-1] = (blocs[-1][0], jour)
        else:
            blocs.append((jour, jour))
    return blocs


def refus_chevauchement_arret(
    nature: Optional[str],
    jours: Iterable[object],
    absences_existantes: Iterable[Mapping[str, object]],
) -> Optional[str]:
    """La phrase de refus si `jours` recouvre un arrêt validé, sinon None."""
    if nature not in IJSS_ELIGIBLE_TYPES:
        return None
    nouveaux = {_jour(j) for j in jours}
    if not nouveaux:
        return None
    existants: set[date] = set()
    natures: dict[date, str] = {}
    lignes: list[tuple[date, date]] = []
    for absence in absences_existantes:
        if absence.get("type") not in IJSS_ELIGIBLE_TYPES:
            continue
        if absence.get("status") not in STATUTS_QUI_COMPTENT:
            continue
        jours_ligne = [_jour(j) for j in absence.get("selected_days") or []]
        if jours_ligne:
            lignes.append((min(jours_ligne), max(jours_ligne)))
        for jour in jours_ligne:
            existants.add(jour)
            natures[jour] = str(absence.get("type"))
    if not existants & nouveaux:
        return None
    debut, fin = next(
        (d, f) for d, f in _blocs(existants) if any(d <= j <= f for j in nouveaux)
    )
    libelle = LIBELLES_NATURE.get(natures[debut], "Arrêt")
    phrase = (
        f"Ce salarié a déjà un arrêt enregistré du {_fr(debut)} au {_fr(fin)} "
        f"({libelle}), qui recouvre la période saisie."
    )
    # Un arrêt importé de la DSN est souvent découpé en plusieurs lignes : on
    # les nomme toutes, chacune s'annule à part.
    concernees = sorted({(d, f) for d, f in lignes if d <= fin and f >= debut})
    if len(concernees) > 1:
        dates = ", ".join(f"du {_fr(d)} au {_fr(f)}" for d, f in concernees)
        annuler = f"annulez les {len(concernees)} arrêts concernés ({dates})"
    else:
        annuler = "annulez-le"
    if nature != natures[debut]:
        # Requalification (L20, capture du 27/11 : arrêt maladie à ressaisir
        # en maladie professionnelle) : un arrêt ne change pas de nature en
        # place, on annule puis on ressaisit. Testée d'abord : une
        # « prolongation » ou des « jours d'avant » d'une autre nature
        # laisseraient l'arrêt existant sous sa nature d'origine.
        ouvrir = "ouvrez-les" if len(concernees) > 1 else "ouvrez-le"
        phrase += (
            f" Pour le requalifier en « {LIBELLES_NATURE.get(str(nature), 'Arrêt')} », "
            f"{ouvrir} dans Arrêts & IJ, {annuler} (« Annuler cet arrêt »), puis "
            "saisissez de nouveau la période avec cette nature. Les bulletins déjà "
            "faits sur ces mois changent quand vous les recalculez."
        )
    elif min(nouveaux) >= debut and max(nouveaux) > fin:
        phrase += (
            f" Pour une prolongation, saisissez la période à partir du "
            f"{_fr(fin + timedelta(days=1))}."
        )
    elif min(nouveaux) < debut and max(nouveaux) <= fin:
        phrase += (
            f" Saisissez seulement les jours d'avant, jusqu'au "
            f"{_fr(debut - timedelta(days=1))}."
        )
    else:
        phrase += f" Pour le remplacer, {annuler}, puis saisissez la bonne période."
    return phrase
