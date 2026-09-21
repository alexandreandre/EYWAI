"""Charge ce qu'il faut pour juger la période à saisir d'un mois.

La fenêtre vient du même endroit que pour le moteur
(`periode_variables_service.resoudre_fenetre_variables`) ; les plannings des
mois couverts par l'union sont lus en une requête par mois ; le contrat borne
la période. Le jugement lui-même est dans `domain.periode_a_saisir`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.payroll.application.periode_variables_service import (
    resoudre_fenetre_variables,
)
from app.modules.schedules.domain.ecart_rules import parse_iso_date
from app.modules.schedules.domain.periode_a_saisir import PeriodeASaisir, periode_a_saisir
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.shared.domain.employment_rules import is_forfait_jour
from app.shared.domain.periode_variables import bornes_mois_civil, semaines_iso


def _mois_couverts(debut: date, fin: date) -> list[tuple[int, int]]:
    mois: list[tuple[int, int]] = []
    annee, m = debut.year, debut.month
    while (annee, m) <= (fin.year, fin.month):
        mois.append((annee, m))
        annee, m = (annee + 1, 1) if m == 12 else (annee, m + 1)
    return mois


def _bornes_contrat(employee: dict[str, Any]) -> tuple[date | None, date | None]:
    """Entrée : `hire_date`. Sortie : dernier jour travaillé de la sortie en cours,
    sinon la fin de contrat — la résolution qu'utilise déjà le STC."""
    entree = parse_iso_date(employee.get("hire_date"))
    sortie = parse_iso_date(
        employee.get("exit_last_working_day") or employee.get("contract_end_date")
    )
    return entree, sortie


def _calendriers(
    ligne: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    if ligne is None:
        return None
    prevu = (ligne.get("planned_calendar") or {}).get("calendrier_prevu") or []
    reel = (ligne.get("actual_hours") or {}).get("calendrier_reel") or []
    return list(prevu), list(reel)


def charger_periodes_a_saisir(
    company_id: str,
    employees: list[dict[str, Any]],
    annee: int,
    mois: int,
) -> dict[str, PeriodeASaisir]:
    """La période à saisir de chaque salarié, en une lecture par mois couvert."""
    fenetre = resoudre_fenetre_variables(str(company_id), annee, mois)
    debut_mois, fin_mois = bornes_mois_civil(annee, mois)
    ids = [str(e["id"]) for e in employees if e.get("id")]
    lignes = {
        cle: schedule_repository.list_schedules_for_employees(ids, cle[0], cle[1])
        for cle in _mois_couverts(min(debut_mois, fenetre.debut), max(fin_mois, fenetre.fin))
    }
    resultat: dict[str, PeriodeASaisir] = {}
    for employee in employees:
        eid = str(employee.get("id") or "")
        if not eid:
            continue
        calendriers = {}
        for cle, par_salarie in lignes.items():
            cal = _calendriers(par_salarie.get(eid))
            if cal is not None:
                calendriers[cle] = cal
        entree, sortie = _bornes_contrat(employee)
        resultat[eid] = periode_a_saisir(
            annee=annee,
            mois=mois,
            fenetre=(fenetre.debut, fenetre.fin),
            calendriers=calendriers,
            date_entree=entree,
            date_sortie=sortie,
            forfait=is_forfait_jour(employee.get("statut"), employee.get("is_forfait_jour")),
            origine=fenetre.origine,
        )
    return resultat


def charger_periode_a_saisir(
    company_id: str, employee: dict[str, Any], annee: int, mois: int
) -> PeriodeASaisir:
    return charger_periodes_a_saisir(company_id, [employee], annee, mois)[str(employee["id"])]


def resume_api(periode: PeriodeASaisir) -> dict[str, Any]:
    """Les champs additifs des réponses (422, avertissements, anomalies)."""
    debut, fin = periode.fenetre
    return {
        "fenetre": {
            "debut": debut.isoformat(),
            "fin": fin.isoformat(),
            "semaines": semaines_iso(debut, fin),
            "origine": periode.origine,
        },
        "jours_manquants": [j.jour.isoformat() for j in periode.bloquants],
        "jours_informatifs": [j.jour.isoformat() for j in periode.informatifs],
    }


__all__ = ["charger_periode_a_saisir", "charger_periodes_a_saisir", "resume_api"]
