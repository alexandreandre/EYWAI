"""Remise du bulletin au salarié (D5) : la date où il le voit, et où il se fige (D4).

« Tout salarié doit recevoir une fiche de paie lors du paiement du salaire » ;
sous forme électronique, l'employeur indique quand elle est disponible
(service-public.fr, F559). La société règle ce jour : le 1er du mois suivant
par défaut (Vanessa et Gaëlle, 29/10), ou dès la validation. Un bulletin remis
ne se reprend plus : une erreur se corrige le mois suivant (Elsa, 29/10).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

from app.shared.domain.temps_local import date_locale

#: Réglage de la société, dans `companies.settings`.
CLE_REGLAGE = "bulletins_mise_a_disposition_jour"
DES_LA_VALIDATION = 0
JOUR_PAR_DEFAUT = 1
JOUR_MAX = 28
#: La tâche quotidienne rattrape les remises de la semaine passée (un jour sans
#: exécution), jamais les anciens bulletins.
JOURS_DE_RATTRAPAGE = 7

_MOIS = (
    "",
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def jour_de_mise_a_disposition(settings: Mapping[str, Any] | None) -> int:
    """0 = dès la validation, sinon le jour du mois suivant (1 à 28)."""
    valeur = (settings or {}).get(CLE_REGLAGE)
    if isinstance(valeur, bool):
        return JOUR_PAR_DEFAUT
    try:
        jour = int(valeur)
    except (TypeError, ValueError):
        return JOUR_PAR_DEFAUT
    if jour < DES_LA_VALIDATION:
        return JOUR_PAR_DEFAUT
    return min(jour, JOUR_MAX)


def _mois_suivant(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def remis_le(
    *,
    year: int,
    month: int,
    statut: str | None,
    valide_le: date | None,
    jour: int,
    bulletin_de_sortie: bool,
) -> date | None:
    """Le jour où le salarié reçoit ce bulletin ; None tant qu'il n'est pas validé.

    Le bulletin du mois de sortie est remis à sa validation : il est payé avec le
    solde de tout compte, le jour du départ.
    """
    if statut != "valide":
        return None
    annee, mois = _mois_suivant(year, month)
    date_du_mois = date(annee, mois, max(jour, 1))
    if valide_le is None:
        return date_du_mois
    if jour == DES_LA_VALIDATION or bulletin_de_sortie:
        return valide_le
    return max(valide_le, date_du_mois)


def _jour_de_validation(valeur: Any) -> date | None:
    if isinstance(valeur, datetime):
        return date_locale(valeur)
    try:
        return date_locale(datetime.fromisoformat(str(valeur or "")))
    except ValueError:
        return None


def remis_le_du_bulletin(bulletin: Mapping[str, Any], *, jour: int) -> date | None:
    """La remise d'un bulletin lu en base : statut, validation (jour de Paris) et
    marque de sortie, dans ses données ou lue à part (`payslip_data->bulletin_de_sortie`)."""
    donnees = bulletin.get("payslip_data")
    sortie = bulletin.get("bulletin_de_sortie")
    if sortie is None and isinstance(donnees, Mapping):
        sortie = donnees.get("bulletin_de_sortie")
    return remis_le(
        year=int(bulletin["year"]),
        month=int(bulletin["month"]),
        statut=bulletin.get("status"),
        valide_le=_jour_de_validation(bulletin.get("validated_at")),
        jour=jour,
        bulletin_de_sortie=sortie is True,
    )


def bulletins_remis(
    bulletins: Iterable[Mapping[str, Any]], *, jour: int, aujourd_hui: date
) -> list[Mapping[str, Any]]:
    """Les bulletins que le salarié voit ce jour-là."""
    return [
        b for b in bulletins if (remis := remis_le_du_bulletin(b, jour=jour)) and remis <= aujourd_hui
    ]


def a_notifier(
    bulletins: Iterable[Mapping[str, Any]], *, jour: int, aujourd_hui: date
) -> list[Mapping[str, Any]]:
    """Les bulletins remis cette semaine dont le salarié n'a pas été prévenu."""
    depuis = aujourd_hui - timedelta(days=JOURS_DE_RATTRAPAGE)
    resultat = []
    for bulletin in bulletins:
        donnees = bulletin.get("payslip_data")
        if isinstance(donnees, Mapping) and donnees.get("salarie_notifie_le"):
            continue
        remis = remis_le_du_bulletin(bulletin, jour=jour)
        if remis and depuis <= remis <= aujourd_hui:
            resultat.append(bulletin)
    return resultat


def message_pas_encore_disponible(remis: date | None) -> str:
    """Le refus fait au salarié qui ouvre un bulletin validé avant sa remise."""
    if remis is None:
        return "Ce bulletin n'est pas encore disponible."
    return f"Ce bulletin sera disponible le {remis:%d/%m/%Y}."


def message_bulletin_remis(year: int, month: int, remis: date) -> str:
    """Le refus de modifier un bulletin remis, et où porter la correction."""
    annee, mois = _mois_suivant(year, month)
    return (
        f"Ce bulletin a été remis au salarié le {remis:%d/%m/%Y} : il ne se modifie plus. "
        f"Une erreur se corrige sur le bulletin de {_MOIS[mois]} {annee}, "
        "par une régularisation."
    )
