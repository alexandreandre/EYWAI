"""Reprise des congés en simulation : le solde qu'affichera MARTINE, sans rien écrire.

`apply_cp_solde_import` lit et écrit dans le même passage : il calcule l'ouverture
des congés, l'écrit, oublie l'ancienne date de reprise, relit le solde affiché et
recale l'ouverture sur le solde importé. Une simulation qui s'arrête avant
l'écriture ne dit donc rien du solde final : c'est pourtant lui qu'il faut
comparer à Quadra (Colorplast, août : une ouverture d'abord tombée à −0,86 au lieu
de −0,43).

Ici, l'écriture des ajustements de congés est gardée en mémoire, et toutes les
lectures des ajustements (ouverture, date de reprise, ajustement applicable)
voient ce qui a été « écrit ». Tout le reste est lu en base dans un bloc
`lecture_seule()` : toute autre écriture est refusée avant de partir, et le droit
d'ancienneté n'est pas enregistré au passage.

Usage :
    with ajustements_en_memoire() as memoire:
        affiche = solde_affiche_apres_reprise(company_id, employee_id, 2026, 9, 3.0, 8.32)
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

#: Les lectures et l'écriture des ajustements de congés, dans le dépôt d'origine.
_NOMS = (
    "upsert_employee_adjustment",
    "get_employee_adjustment",
    "get_applicable_adjustment",
    "get_applicable_adjustments_by_employees",
    "get_adjustments_by_employees_year",
)
_NOM_DATE_DE_REPRISE = "get_cp_opening_reference_dates"


class Memoire:
    """Les lignes d'ajustement « écrites » pendant la simulation, par (salarié, année)."""

    def __init__(self) -> None:
        self.lignes: dict[tuple[str, int], dict[str, Any]] = {}

    def lignes_du_salarie(self, employee_id: str) -> list[dict[str, Any]]:
        """Les lignes en base du salarié, toutes années, avec celles de la mémoire par-dessus."""
        from app.core.database import supabase

        en_base = (
            supabase.table("employee_leave_adjustments")
            .select("*")
            .eq("employee_id", str(employee_id))
            .execute()
            .data
            or []
        )
        par_annee = {int(r.get("year") or 0): dict(r) for r in en_base}
        for (eid, annee), ligne in self.lignes.items():
            if eid == str(employee_id):
                par_annee[annee] = {**par_annee.get(annee, {}), **ligne}
        return list(par_annee.values())


@contextmanager
def ajustements_en_memoire() -> Iterator[Memoire]:
    """Le temps du bloc : ajustements de congés en mémoire, base en lecture seule."""
    # Les modules qui lisent ou écrivent les ajustements, importés avant le
    # remplacement : un import plus tardif garderait les fonctions d'origine.
    import app.modules.absences.application.leave_settings_commands
    import app.modules.absences.application.queries  # noqa: F401
    from app.core.lecture_seule import lecture_seule
    from app.modules.absences.infrastructure import leave_settings_repository as depot
    from app.modules.absences.infrastructure import planning_cp_repository as planning
    from app.modules.absences.infrastructure.repository import oublier_dates_de_reprise

    memoire = Memoire()

    def upsert_employee_adjustment(company_id, employee_id, year, data):
        cle = (str(employee_id), int(year))
        courante = next(
            (r for r in memoire.lignes_du_salarie(employee_id) if int(r.get("year") or 0) == int(year)),
            {},
        )
        memoire.lignes[cle] = {
            **courante,
            **data,
            "company_id": company_id,
            "employee_id": str(employee_id),
            "year": int(year),
        }
        return dict(memoire.lignes[cle])

    def get_employee_adjustment(employee_id, year):
        ligne = next(
            (r for r in memoire.lignes_du_salarie(employee_id) if int(r.get("year") or 0) == int(year)),
            None,
        )
        return depot._row_to_adjustment(ligne)

    def get_applicable_adjustment(employee_id, year):
        return depot.resoudre_ajustement_applicable(memoire.lignes_du_salarie(employee_id), year)

    def get_applicable_adjustments_by_employees(employee_ids, year):
        return {
            str(eid): depot.resoudre_ajustement_applicable(memoire.lignes_du_salarie(eid), year)
            for eid in employee_ids or []
        }

    def get_adjustments_by_employees_year(employee_ids, year):
        sortie = {}
        for eid in employee_ids or []:
            ligne = next(
                (r for r in memoire.lignes_du_salarie(eid) if int(r.get("year") or 0) == int(year)),
                None,
            )
            if ligne:
                sortie[str(eid)] = depot._row_to_adjustment(ligne)
        return sortie

    def get_cp_opening_reference_dates(employee_ids):
        dates: dict[str, date | None] = {}
        for eid in employee_ids or []:
            for ligne in memoire.lignes_du_salarie(eid):
                brut = ligne.get("cp_opening_reference_date")
                if not brut:
                    continue
                valeur = date.fromisoformat(str(brut)[:10])
                if dates.get(str(eid)) is None or valeur > dates[str(eid)]:
                    dates[str(eid)] = valeur
        return dates

    remplacants = {
        "upsert_employee_adjustment": upsert_employee_adjustment,
        "get_employee_adjustment": get_employee_adjustment,
        "get_applicable_adjustment": get_applicable_adjustment,
        "get_applicable_adjustments_by_employees": get_applicable_adjustments_by_employees,
        "get_adjustments_by_employees_year": get_adjustments_by_employees_year,
        _NOM_DATE_DE_REPRISE: get_cp_opening_reference_dates,
    }
    originaux = {nom: getattr(depot, nom) for nom in _NOMS}
    originaux[_NOM_DATE_DE_REPRISE] = getattr(planning, _NOM_DATE_DE_REPRISE)

    # Chaque module qui a importé l'une de ces fonctions par son nom en garde sa
    # propre référence : on les remplace toutes, puis on les remet.
    poses: list[tuple[Any, str, Any]] = []
    for module in list(sys.modules.values()):
        if module is None or not str(getattr(module, "__name__", "")).startswith("app."):
            continue
        for nom, origine in originaux.items():
            if getattr(module, nom, None) is origine:
                poses.append((module, nom, origine))
                setattr(module, nom, remplacants[nom])
    oublier_dates_de_reprise()
    try:
        with lecture_seule():
            yield memoire
    finally:
        for module, nom, origine in poses:
            setattr(module, nom, origine)
        oublier_dates_de_reprise()


def _soldes(affiche: dict | None) -> tuple[float, float] | None:
    if not affiche:
        return None
    n1 = (affiche.get("conges_payes_periode_precedente") or {}).get("solde")
    n = (affiche.get("conges_payes") or {}).get("solde")
    return round(float(n1 or 0.0), 2), round(float(n or 0.0), 2)


def solde_affiche(employee_id: str, annee: int, mois: int) -> tuple[float, float] | None:
    """(N-1, N) affichés au bulletin du mois, tels que la base les donne aujourd'hui."""
    from app.modules.absences.application.queries import (
        get_absence_balances_for_payslip,
    )

    return _soldes(get_absence_balances_for_payslip(str(employee_id), annee, mois))


def solde_affiche_apres_reprise(
    company_id: str,
    employee_id: str,
    annee: int,
    mois: int,
    cp_n1: float,
    cp_n: float,
    *,
    note: str | None = None,
) -> tuple[float, float] | None:
    """(N-1, N) affichés au bulletin du mois après `apply_cp_solde_import`, simulé.

    À appeler dans un bloc `ajustements_en_memoire()`. None : aucun compteur au
    bulletin de ce mois (fiche sortie avant le mois, par exemple).
    """
    from app.modules.absences.application.leave_settings_commands import (
        apply_cp_solde_import,
    )

    apply_cp_solde_import(
        company_id, str(employee_id), annee,
        cp_n1_solde=float(cp_n1), cp_n_solde=float(cp_n), rtt_solde=0.0, month=mois,
        note=note,
    )
    return solde_affiche(employee_id, annee, mois)
