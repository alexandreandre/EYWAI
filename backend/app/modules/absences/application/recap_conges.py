"""Récapitulatif des congés et absences de la société (lot L21, 28/11/2026).

Lecture seule : lit les salariés, leurs mois de calendrier et leurs demandes
validées, puis les soldes CP de l'aperçu des soldes déjà utilisé par
l'écran « Entreprise, onglet Paie, Congés & RTT ». Le décompte est dans
`domain.recap_conges`.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Optional

from app.core.database import supabase
from app.modules.absences.application import leave_settings_queries
from app.modules.absences.domain.recap_conges import (
    COLONNES,
    NOTE_ARRETS,
    SOURCE_SOLDES_CP,
    TYPES_DEMANDE_HORS_CALENDRIER,
    construire_recap,
    lignes_du_fichier,
    lire_periode,
    mois_de_la_periode,
)
from app.modules.absences.infrastructure.pagination import fetch_all_rows
from app.shared.utils.export import generate_xlsx_feuilles

_TYPES_DEMANDES_LUES = sorted(set(TYPES_DEMANDE_HORS_CALENDRIER) | {"sans_solde"})


def _par_lots(ids: list[str], taille: int = 150) -> Iterable[list[str]]:
    for i in range(0, len(ids), taille):
        yield ids[i : i + taille]


def lire_employes(company_id: str) -> list[dict[str, Any]]:
    def page(offset: int, size: int) -> list[dict[str, Any]]:
        return (
            supabase.table("employees")
            .select("id, first_name, last_name, nom_usage, matricule, employment_status")
            .eq("company_id", company_id)
            .order("id")
            .range(offset, offset + size - 1)
            .execute()
            .data
            or []
        )

    return fetch_all_rows(page)


def lire_calendriers(employee_ids: list[str], debut: date, fin: date) -> list[dict[str, Any]]:
    mois = set(mois_de_la_periode(debut, fin))
    lignes: list[dict[str, Any]] = []
    for lot in _par_lots(employee_ids):

        def page(offset: int, size: int, lot: list[str] = lot) -> list[dict[str, Any]]:
            return (
                supabase.table("employee_schedules")
                .select("employee_id, year, month, planned_calendar")
                .in_("employee_id", lot)
                .gte("year", debut.year)
                .lte("year", fin.year)
                .order("id")
                .range(offset, offset + size - 1)
                .execute()
                .data
                or []
            )

        lignes.extend(l for l in fetch_all_rows(page) if (l.get("year"), l.get("month")) in mois)
    return lignes


def lire_demandes_validees(employee_ids: list[str]) -> list[dict[str, Any]]:
    lignes: list[dict[str, Any]] = []
    for lot in _par_lots(employee_ids):

        def page(offset: int, size: int, lot: list[str] = lot) -> list[dict[str, Any]]:
            return (
                supabase.table("absence_requests")
                .select("employee_id, type, event_subtype, selected_days, demi_journees")
                .in_("employee_id", lot)
                .eq("status", "validated")
                .in_("type", _TYPES_DEMANDES_LUES)
                .order("id")
                .range(offset, offset + size - 1)
                .execute()
                .data
                or []
            )

        lignes.extend(fetch_all_rows(page))
    return lignes


def lire_soldes_cp(company_id: str) -> dict[str, dict[str, float]]:
    """Soldes CP N-1 et N de l'aperçu des soldes (salariés actifs, date du jour)."""
    apercu = leave_settings_queries.get_leave_balances_overview(company_id, None)
    return {
        str(item.employee_id): {"cp_n1": item.cp_n1_remaining, "cp_n": item.cp_n_remaining}
        for item in apercu.employees
    }


def get_recap_conges(
    company_id: str,
    debut: Optional[str],
    fin: Optional[str],
    employes_autorises: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Le récapitulatif de la période ; `employes_autorises` None = toute la société."""
    d0, d1 = lire_periode(debut, fin)
    employes = lire_employes(company_id)
    if employes_autorises is not None:
        employes = [e for e in employes if str(e.get("id")) in employes_autorises]
    ids = [str(e["id"]) for e in employes]
    return construire_recap(
        debut=d0,
        fin=d1,
        employes=employes,
        calendriers=lire_calendriers(ids, d0, d1) if ids else [],
        demandes_validees=lire_demandes_validees(ids) if ids else [],
        soldes=lire_soldes_cp(company_id) if ids else {},
        date_des_soldes=date.today(),
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
