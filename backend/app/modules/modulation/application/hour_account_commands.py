"""Commands compte d'heures modulation."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.modulation.application.hour_account_queries import (
    sync_account_balance_cache,
    _movement_row_to_schema,
)
from app.modules.modulation.infrastructure import overtime_routing_repository as otr_repo
from app.modules.modulation.infrastructure import repository as repo
from app.modules.modulation.schemas.requests import ModulationMovementSchema


def create_opening_balance(
    company_id: str,
    employee_id: str,
    hours: float,
    *,
    note: str | None = None,
    validated_by: str | None = None,
    year: int | None = None,
) -> ModulationMovementSchema:
    ref_year = year or date.today().year
    row = repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": ref_year,
            "month": None,
            "movement_type": "opening_balance",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "manual_rh",
            "note": note,
            "validated_by": validated_by,
        }
    )
    sync_account_balance_cache(company_id, employee_id, ref_year)
    return _movement_row_to_schema(row)


def create_manual_adjustment(
    company_id: str,
    employee_id: str,
    hours: float,
    *,
    note: str | None = None,
    validated_by: str | None = None,
    year: int | None = None,
) -> ModulationMovementSchema:
    ref_year = year or date.today().year
    row = repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": ref_year,
            "month": date.today().month,
            "movement_type": "adjustment",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "manual_rh",
            "note": note,
            "validated_by": validated_by,
        }
    )
    sync_account_balance_cache(company_id, employee_id, ref_year)
    return _movement_row_to_schema(row)


def create_credit_hs_movement(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    hours: float,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "movement_type": "credit_hs",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "payroll_auto",
            "metadata": metadata or {},
        }
    )


def create_debit_recovery_movement(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    hours: float,
    *,
    reference_id: str,
    note: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "movement_type": "debit_recovery",
            "hours": round(float(hours), 2),
            "status": "validated",
            "source": "absence",
            "reference_id": reference_id,
            "note": note,
            "metadata": metadata or {},
        }
    )
    sync_account_balance_cache(company_id, employee_id, year)
    return row


def annuler_debits_de_recuperation(request_id: str) -> int:
    """Une récupération annulée rend ses heures : ses débits passent à
    « annulé » (gardés pour la trace, hors du solde)."""
    lignes = repo.annuler_mouvements_de_reference(request_id, "debit_recovery")
    for ligne in lignes:
        sync_account_balance_cache(
            str(ligne["company_id"]), str(ligne["employee_id"]), int(ligne["year"])
        )
    return len(lignes)


def payer_le_solde(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    heures: float,
    *,
    par: str | None = None,
) -> dict[str, Any]:
    """Payer des heures du compteur sur le bulletin du mois (solde de janvier,
    départ…) : un débit « paiement » ; le bulletin du mois porte la prime."""
    from app.modules.modulation.domain.hour_account_rules import solde_payable

    heures = round(float(heures), 2)
    if heures <= 0:
        raise ValueError("Indiquez un nombre d'heures à payer.")
    solde = solde_payable(repo.list_movements_for_employee(employee_id), year, month)
    if heures > solde:
        texte = f"{solde:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        raise ValueError(
            f"Il n'y a que {texte} h à payer comme solde sur ce bulletin : les heures "
            "mises au compteur ce mois-ci se paient avec « Payer ces heures ce mois-ci »."
        )
    row = repo.insert_movement(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "movement_type": "debit_payout",
            "hours": heures,
            "status": "validated",
            "source": "manual_rh",
            "validated_by": par,
            "note": "Paiement du solde de récupération",
        }
    )
    sync_account_balance_cache(company_id, employee_id, year)
    return row


def annuler_paiement_du_mois(company_id: str, employee_id: str, year: int, month: int) -> int:
    """Les heures payées sur le bulletin du mois reviennent au compteur."""
    lignes = repo.annuler_paiements_du_mois(employee_id, year, month)
    if lignes:
        sync_account_balance_cache(company_id, employee_id, year)
    return len(lignes)


def choisir_le_mois(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    *,
    choix: str,
    heures_sup: float,
    par: str | None = None,
) -> None:
    """Le choix du mois pour un salarié : « payer » ces heures, les mettre au
    « compteur », ou revenir à la « regle » de la société.

    La décision du mois l'emporte sur la règle ; sans décision, la règle joue."""
    if choix == "regle":
        otr_repo.supprimer_decision(employee_id, year, month)
        return
    heures = round(max(0.0, float(heures_sup or 0)), 2)
    au_compteur = choix == "compteur"
    otr_repo.upsert_decision(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "total_hs_hours": heures,
            "hours_to_pay": 0 if au_compteur else heures,
            "hours_to_account": heures if au_compteur else 0,
            "status": "validated",
            "decided_by": par,
            "note": "Mises au compteur ce mois-ci" if au_compteur else "Payées ce mois-ci au lieu du compteur",
        }
    )
