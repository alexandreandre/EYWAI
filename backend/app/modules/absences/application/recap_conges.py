"""Récapitulatif des congés et absences de la société (lot L21, 28/11/2026).

Lecture seule de bout en bout (`lecture_seule()`) : aucune écriture ne peut
partir, pas même le droit à congés d'ancienneté que l'aperçu des soldes
enregistre au passage. Moins de dix lectures, quel que soit l'effectif (au
plus 150 salariés par lecture), les plus longues en parallèle :

1. les salariés de la société ;
2. leurs mois de calendrier de la période (une lecture par année touchée) ;
3. leurs demandes validées, avec les congés payés du calendrier (deux lectures) ;
4. leurs dates de reprise de solde ;
5. pour les soldes : règles de congés, règles d'ancienneté, ajustements.

Le décompte est dans `domain.recap_conges`.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any, Iterable, Optional

from app.core.database import supabase
from app.core.lecture_seule import lecture_seule
from app.modules.absences.application.cp_seniority_queries import (
    build_employee_cp_seniority_context,
    employee_cp_seniority_select,
)
from app.modules.absences.domain.recap_conges import (
    COLONNES,
    NOTE_ARRETS,
    NOTE_REPRISE,
    SOURCE_SOLDES_CP,
    construire_recap,
    est_present,
    lignes_du_fichier,
    mois_de_la_periode,
)
from app.modules.absences.domain.rules import compute_absence_balances
from app.modules.absences.infrastructure import planning_cp_repository
from app.modules.absences.infrastructure.cp_seniority_repository import get_cp_seniority_settings
from app.modules.absences.infrastructure.leave_settings_repository import (
    get_applicable_adjustments_by_employees,
    get_leave_policy,
)
from app.modules.absences.infrastructure.pagination import fetch_all_rows
from app.modules.absences.infrastructure.repository import absence_repository
from app.shared.domain.conge_parental import est_conge_parental
from app.shared.utils.export import generate_xlsx_feuilles


def _par_lots(ids: list[str], taille: int = 150) -> Iterable[list[str]]:
    for i in range(0, len(ids), taille):
        yield ids[i : i + taille]


def lire_employes(company_id: str) -> list[dict[str, Any]]:
    champs = f"{employee_cp_seniority_select(include_id=True, include_status=True)}, nom_usage, matricule"

    def page(offset: int, size: int) -> list[dict[str, Any]]:
        return (
            supabase.table("employees")
            .select(champs)
            .eq("company_id", company_id)
            .order("id")
            .range(offset, offset + size - 1)
            .execute()
            .data
            or []
        )

    return fetch_all_rows(page)


def lire_calendriers(employee_ids: list[str], debut: date, fin: date) -> list[dict[str, Any]]:
    """Les seuls mois de la période : une lecture par année touchée (et par lot de salariés)."""
    mois_par_annee: dict[int, list[int]] = {}
    for annee, mois in mois_de_la_periode(debut, fin):
        mois_par_annee.setdefault(annee, []).append(mois)
    lignes: list[dict[str, Any]] = []
    for annee, mois in mois_par_annee.items():
        for lot in _par_lots(employee_ids):

            def page(offset: int, size: int, lot: list[str] = lot, annee: int = annee, mois: list[int] = mois):
                return (
                    supabase.table("employee_schedules")
                    .select("employee_id, year, month, planned_calendar")
                    .in_("employee_id", lot)
                    .eq("year", annee)
                    .in_("month", mois)
                    .order("id")
                    .range(offset, offset + size - 1)
                    .execute()
                    .data
                    or []
                )

            lignes.extend(fetch_all_rows(page))
    return lignes


def lire_demandes_validees(employee_ids: list[str]) -> list[dict[str, Any]]:
    """Demandes validées et congés payés du calendrier : la lecture des soldes."""
    return absence_repository.list_validated_for_employees(employee_ids)


def lire_reprises(employee_ids: list[str]) -> dict[str, Optional[date]]:
    return planning_cp_repository.get_cp_opening_reference_dates(employee_ids)


def _date(valeur: Any) -> Optional[date]:
    if not valeur:
        return None
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _presents_avec_entree(employes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in employes if est_present(e) and _date(e.get("hire_date"))]


def charger_regles_des_soldes(
    company_id: str, employee_ids: list[str], annee: int
) -> tuple[Any, Any, dict[str, Any]]:
    """Règles de congés, règles d'ancienneté, ajustements de l'année : trois lectures."""
    return (
        get_leave_policy(company_id),
        get_cp_seniority_settings(company_id),
        get_applicable_adjustments_by_employees(employee_ids, annee) if employee_ids else {},
    )


def _en_parallele(fonction, *args):
    """Lance une lecture dans un fil, avec le contexte du bloc de lecture seule."""
    return contextvars.copy_context().run, fonction, *args


def soldes_cp(
    company_id: str,
    employes: list[dict[str, Any]],
    demandes_validees: list[dict[str, Any]],
    aujourd_hui: date,
    regles: Optional[tuple[Any, Any, dict[str, Any]]] = None,
) -> dict[str, dict[str, float]]:
    """CP N-1 et N au jour, des salariés présents du périmètre, comme la fiche salarié.

    Seulement `compute_absence_balances` : ni droit d'ancienneté enregistré, ni
    droit de fractionnement relu. Les congés parentaux validés comptent pour
    l'ancienneté, comme sur la fiche.
    """
    presents = _presents_avec_entree(employes)
    if not presents:
        return {}
    policy, cp_seniority, ajustements = regles or charger_regles_des_soldes(
        company_id, [str(e["id"]) for e in presents], aujourd_hui.year
    )
    demandes_par_salarie: dict[str, list[dict[str, Any]]] = {}
    for demande in demandes_validees:
        demandes_par_salarie.setdefault(str(demande.get("employee_id")), []).append(demande)

    soldes: dict[str, dict[str, float]] = {}
    for employe in presents:
        eid = str(employe["id"])
        demandes = demandes_par_salarie.get(eid, [])
        contexte = build_employee_cp_seniority_context(
            employe, [d for d in demandes if est_conge_parental(d)]
        )
        calcul = compute_absence_balances(
            _date(employe.get("hire_date")),
            demandes,
            aujourd_hui,
            policy=policy,
            adjustment=ajustements.get(eid),
            cp_seniority=cp_seniority,
            employee_ctx=contexte,
        )
        n1 = calcul.get("conges_payes_n1") or {}
        n = calcul.get("conges_payes_n") or {}
        soldes[eid] = {
            "cp_n1": max(0.0, float(n1.get("solde", 0))),
            "cp_n": max(0.0, float(n.get("solde", 0))),
        }
    return soldes


def get_recap_conges(
    company_id: str,
    debut: date,
    fin: date,
    employes_autorises: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Le récapitulatif de la période ; `employes_autorises` None = toute la société."""
    aujourd_hui = date.today()
    with lecture_seule():
        employes = lire_employes(company_id)
        if employes_autorises is not None:
            employes = [e for e in employes if str(e.get("id")) in employes_autorises]
        ids = [str(e["id"]) for e in employes]
        if not ids:
            calendriers, demandes, reprises, soldes = [], [], {}, {}
        else:
            ids_soldes = [str(e["id"]) for e in _presents_avec_entree(employes)]
            # Les demandes validées (avec les congés payés de tout le calendrier)
            # sont la lecture longue : les autres partent pendant ce temps.
            with ThreadPoolExecutor(max_workers=3) as fils:
                f_demandes = fils.submit(*_en_parallele(lire_demandes_validees, ids))
                f_regles = fils.submit(
                    *_en_parallele(charger_regles_des_soldes, company_id, ids_soldes, aujourd_hui.year)
                )
                f_calendriers = fils.submit(*_en_parallele(lire_calendriers, ids, debut, fin))
                demandes = f_demandes.result()
                regles = f_regles.result()
                calendriers = f_calendriers.result()
            reprises = lire_reprises(ids)
            soldes = soldes_cp(company_id, employes, demandes, aujourd_hui, regles)
    return construire_recap(
        debut=debut,
        fin=fin,
        employes=employes,
        calendriers=calendriers,
        demandes_validees=demandes,
        soldes=soldes,
        date_des_soldes=aujourd_hui,
        reprises=reprises,
    )


def nom_du_fichier(recap: dict[str, Any]) -> str:
    return f"recap-conges-{recap['debut']}-{recap['fin']}.xlsx"


def recap_en_xlsx(recap: dict[str, Any]) -> bytes:
    """Deux feuilles : le récapitulatif, et d'où vient chaque colonne."""
    entetes, lignes = lignes_du_fichier(recap)
    sources = [
        {"Colonne": f"{libelle} (j)", "Source": source} for _cle, libelle, source in COLONNES
    ]
    sources.append({"Colonne": "Arrêts", "Source": NOTE_ARRETS})
    sources.append({"Colonne": "Solde CP N-1 (j) / Solde CP N (j)", "Source": SOURCE_SOLDES_CP})
    sources.append({"Colonne": "Reprise dans Martine", "Source": NOTE_REPRISE})
    sources.append(
        {
            "Colonne": "Période",
            "Source": f"du {recap['debut']} au {recap['fin']} ; soldes au {recap['date_des_soldes']}",
        }
    )
    return generate_xlsx_feuilles(
        [
            ("Récapitulatif", entetes, lignes),
            ("Sources", ["Colonne", "Source"], sources),
        ]
    )
