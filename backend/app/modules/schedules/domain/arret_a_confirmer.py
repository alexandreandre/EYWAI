"""Un arrêt qui court au tournant du mois et n'est pas reposé le mois suivant.

Sans arrêt saisi, le planning du mois est payé plein : c'est l'erreur la plus
probable des premiers mois après la reprise (un arrêt repris qui finit le jour
de la bascule et n'est pas prolongé, D5). Module pur.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Iterable, Mapping, Optional

from app.modules.schedules.domain.conflits_arret import est_un_arret
from app.modules.schedules.domain.ecart_rules import month_period_bounds


def _dernier_jour_ouvre(annee: int, mois: int) -> date:
    jour = date(annee, mois, monthrange(annee, mois)[1])
    while jour.weekday() >= 5:
        jour -= timedelta(days=1)
    return jour


def _borne(valeur: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valeur)[:10]) if valeur else None
    except ValueError:
        return None


def _porte_un_arret(jour: Mapping[str, Any]) -> bool:
    return est_un_arret(str(jour.get("type") or "")) or bool(jour.get("date_debut_arret_reel"))


def fin_de_l_arret_au_tournant(
    calendrier_precedent: Iterable[Any], annee: int, mois: int
) -> Optional[date]:
    """La fin du dernier arrêt qui court jusqu'au dernier jour ouvré du mois, sinon None."""
    fin: Optional[date] = None
    for jour in calendrier_precedent or []:
        if not isinstance(jour, Mapping) or not _porte_un_arret(jour):
            continue
        try:
            du_jour = date(annee, mois, int(jour.get("jour") or 0))
        except (TypeError, ValueError):
            continue
        fin_du_jour = max(_borne(jour.get("date_fin_arret_reel")) or du_jour, du_jour)
        fin = max(fin, fin_du_jour) if fin else fin_du_jour
    if fin is None or fin < _dernier_jour_ouvre(annee, mois):
        return None
    return fin


def arret_saisi_au_mois(
    calendrier: Iterable[Any], absences: Iterable[Mapping[str, Any]], annee: int, mois: int
) -> bool:
    """Le mois porte un arrêt : au planning, ou par une demande validée."""
    if any(isinstance(j, Mapping) and _porte_un_arret(j) for j in calendrier or []):
        return True
    debut, fin = month_period_bounds(annee, mois)
    for demande in absences or []:
        if not est_un_arret(str(demande.get("type") or "")):
            continue
        for brut in demande.get("selected_days") or []:
            jour = _borne(brut)
            if jour and debut <= jour <= fin:
                return True
    return False


def _reprise_constatee(prevus: Iterable[Any], reels: Iterable[Any]) -> bool:
    """Le premier jour de travail prévu du mois porte des heures faites."""
    premier = next(
        (j.get("jour") for j in prevus or [] if isinstance(j, Mapping) and j.get("type") == "travail"),
        None,
    )
    if premier is None:
        return False
    for jour in reels or []:
        if isinstance(jour, Mapping) and jour.get("jour") == premier:
            try:
                return float(jour.get("heures_faites") or 0) > 0
            except (TypeError, ValueError):
                return False
    return False


def message_arret_a_confirmer(fin: date, annee: int, mois: int) -> str:
    libelle_mois = f"{mois:02d}/{annee}"
    if fin >= date(annee, mois, 1):
        return (
            f"Arrêt en cours jusqu'au {fin:%d/%m} d'après le mois précédent, aucun arrêt saisi "
            f"en {libelle_mois} : sans saisie, le mois part payé plein. Saisissez l'arrêt ou sa "
            "prolongation dans le planning."
        )
    return (
        f"Arrêt terminé le {fin:%d/%m}, à la fin du mois précédent, et aucune prolongation saisie "
        f"en {libelle_mois} : s'il a été prolongé, le mois part payé plein. Confirmez la reprise, "
        "ou saisissez la prolongation dans le planning."
    )


def fin_d_arret_a_confirmer(
    calendrier_precedent: Iterable[Any],
    prevus: Iterable[Any],
    reels: Iterable[Any],
    absences: Iterable[Mapping[str, Any]],
    annee: int,
    mois: int,
) -> Optional[date]:
    """La fin de l'arrêt à confirmer pour ce salarié ce mois-ci, sinon None."""
    annee_prec, mois_prec = (annee - 1, 12) if mois == 1 else (annee, mois - 1)
    fin = fin_de_l_arret_au_tournant(calendrier_precedent, annee_prec, mois_prec)
    if fin is None or arret_saisi_au_mois(prevus, absences, annee, mois):
        return None
    # Des heures faites le premier jour prouvent la reprise, sauf si l'arrêt court encore.
    if fin < date(annee, mois, 1) and _reprise_constatee(prevus, reels):
        return None
    return fin
