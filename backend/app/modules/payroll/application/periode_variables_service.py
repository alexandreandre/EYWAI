"""
Point d'entrée unique de la fenêtre des variables.

Trois consommateurs l'appellent : le moteur de bulletin, l'agrégateur de postes
(paniers d'équipe) et le générateur de variables mensuelles. Ils doivent lire la
même fenêtre, sinon les heures sup décalent et les paniers non.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.database import supabase
from app.modules.payroll.engine.period_forfait import bornes_periode_de_paie
from app.modules.payroll.infrastructure.variable_periods_repository import (
    get_variable_period,
    upsert_variable_period,
)
from app.shared.domain.periode_de_paie import periode_de_paie_depuis_societe
from app.shared.domain.periode_variables import (
    ORIGINE_MANUEL,
    FenetreVariables,
    bornes_mois_civil,
    normaliser_fin_semaine,
    resoudre_fenetre,
    semaines_iso,
)


def _charger_societe(company_id: str) -> dict[str, Any]:
    resp = (
        supabase.table("companies")
        .select("id, paie_jour_de_fin, paie_occurrence")
        .eq("id", str(company_id))
        .maybe_single()
        .execute()
    )
    return (resp.data if resp else None) or {}


def _mois_precedent(annee: int, mois: int) -> tuple[int, int]:
    return (annee - 1, 12) if mois == 1 else (annee, mois - 1)


def _bornes_regle(societe: dict[str, Any], annee: int, mois: int) -> tuple[date, date]:
    regles = periode_de_paie_depuis_societe(societe)
    return bornes_periode_de_paie(
        annee, mois, regles["jour_de_fin"], regles["occurrence"]
    )


def _fin_retenue(
    societe: dict[str, Any], company_id: str, annee: int, mois: int
) -> date:
    """Fin réellement appliquée à un mois : sa surcharge, sinon sa règle."""
    ligne = get_variable_period(str(company_id), annee, mois)
    if ligne and ligne.get("end_date"):
        return date.fromisoformat(str(ligne["end_date"])[:10])
    return _bornes_regle(societe, annee, mois)[1]


def resoudre_fenetre_variables(
    company_id: str,
    annee: int,
    mois: int,
    societe: dict[str, Any] | None = None,
) -> FenetreVariables:
    """Fenêtre effective des variables pour (société, mois)."""
    societe = societe if societe is not None else _charger_societe(str(company_id))
    bornes = _bornes_regle(societe, annee, mois)

    annee_prec, mois_prec = _mois_precedent(annee, mois)
    fin_precedente = _fin_retenue(societe, str(company_id), annee_prec, mois_prec)

    ligne = get_variable_period(str(company_id), annee, mois)
    surcharge = (
        date.fromisoformat(str(ligne["end_date"])[:10])
        if ligne and ligne.get("end_date")
        else None
    )
    return resoudre_fenetre(
        bornes_regle=bornes,
        fin_mois_precedent=fin_precedente,
        surcharge=surcharge,
    )


def enregistrer_fenetre_variables(
    company_id: str,
    annee: int,
    mois: int,
    fin: date,
    user_id: str | None = None,
) -> FenetreVariables:
    """Enregistre l'arrêt choisi, normalisé à la semaine complète."""
    societe = _charger_societe(str(company_id))
    annee_prec, mois_prec = _mois_precedent(annee, mois)
    debut = _fin_retenue(societe, str(company_id), annee_prec, mois_prec) + timedelta(
        days=1
    )
    fin_normalisee = normaliser_fin_semaine(fin)
    if fin_normalisee < debut:
        raise ValueError(
            f"Fin de fenêtre ({fin_normalisee:%d/%m/%Y}) antérieure à son début "
            f"({debut:%d/%m/%Y})."
        )
    upsert_variable_period(
        company_id=str(company_id),
        annee=annee,
        mois=mois,
        debut=debut,
        fin=fin_normalisee,
        origine=ORIGINE_MANUEL,
        user_id=user_id,
    )
    return FenetreVariables(debut=debut, fin=fin_normalisee, origine=ORIGINE_MANUEL)


def apercu_fenetre(company_id: str, annee: int, mois: int) -> dict[str, Any]:
    """Charge utile de l'API : la fenêtre plus de quoi l'afficher sans recalcul."""
    fenetre = resoudre_fenetre_variables(str(company_id), annee, mois)
    debut_mois, fin_mois = bornes_mois_civil(annee, mois)
    return {
        "debut": fenetre.debut.isoformat(),
        "fin": fenetre.fin.isoformat(),
        "origine": fenetre.origine,
        "semaines": semaines_iso(fenetre.debut, fenetre.fin),
        "mois_civil": [debut_mois.isoformat(), fin_mois.isoformat()],
        "report_debut": (fenetre.fin + timedelta(days=1)).isoformat(),
    }


__all__ = [
    "apercu_fenetre",
    "enregistrer_fenetre_variables",
    "resoudre_fenetre_variables",
]
