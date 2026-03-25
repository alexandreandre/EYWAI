# moteur_paie/period_forfait.py
"""
Définition de la période de paie pour le forfait jour.
Logique extraite de backend_calculs/generateur_fiche_paie_forfait.py pour être appelée depuis app.modules.payroll.
"""

import calendar
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contexte import ContextePaie


def _get_end_date_for_month(
    target_annee: int,
    target_mois: int,
    jour_cible: int,
    occurrence_cible: int,
) -> date:
    """
    Trouve une date en se basant sur un jour de la semaine et son occurrence dans le mois.
    jour_cible: 0 pour Lundi, ..., 6 pour Dimanche.
    occurrence_cible: 1 pour le premier, -1 pour le dernier.
    """
    _, num_days = calendar.monthrange(target_annee, target_mois)

    jours_trouves = [
        date(target_annee, target_mois, day)
        for day in range(1, num_days + 1)
        if date(target_annee, target_mois, day).weekday() == jour_cible
    ]

    if not jours_trouves:
        raise ValueError(
            f"Aucun jour correspondant au jour {jour_cible} trouvé pour {target_mois}/{target_annee}."
        )

    try:
        if occurrence_cible > 0:
            return jours_trouves[occurrence_cible - 1]
        return jours_trouves[occurrence_cible]
    except IndexError:
        raise ValueError(
            f"L'occurrence {occurrence_cible} est invalide pour le mois de {target_mois}/{target_annee}."
        )


def definir_periode_de_paie(
    contexte: "ContextePaie", annee: int, mois: int
) -> tuple[date, date]:
    """
    Détermine la période de paie en lisant les règles depuis la configuration de l'entreprise.
    La période de travail s'arrête le dimanche de la semaine du jour de référence.
    """
    regles_paie = contexte.entreprise.get("parametres_paie", {}).get(
        "periode_de_paie", {}
    )
    jour_reference = regles_paie.get("jour_de_fin", 4)  # Vendredi par défaut
    occurrence_reference = regles_paie.get("occurrence", -2)  # Avant-dernier par défaut

    date_de_reference = _get_end_date_for_month(
        annee, mois, jour_reference, occurrence_reference
    )

    decalage_vers_dimanche = 6 - date_de_reference.weekday()
    date_fin_periode = date_de_reference + timedelta(days=decalage_vers_dimanche)

    mois_precedent = mois - 1
    annee_precedente = annee
    if mois_precedent == 0:
        mois_precedent = 12
        annee_precedente -= 1

    date_de_reference_precedente = _get_end_date_for_month(
        annee_precedente, mois_precedent, jour_reference, occurrence_reference
    )

    decalage_vers_dimanche_precedent = 6 - date_de_reference_precedente.weekday()
    date_fin_periode_precedente = date_de_reference_precedente + timedelta(
        days=decalage_vers_dimanche_precedent
    )

    date_debut_periode = date_fin_periode_precedente + timedelta(days=1)

    return date_debut_periode, date_fin_periode
