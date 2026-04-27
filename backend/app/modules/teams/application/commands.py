"""Commandes applicatives — module Équipes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.teams.infrastructure.repository import teams_repository
from app.modules.teams.schemas.requests import TeamCreate, TeamUpdate


def create_team(data: TeamCreate, company_id: str) -> dict:
    """
    1. Vérifie unicité nom (insensible casse) via check_name_exists.
    2. Insert avec company_id.
    3. Retourne le team créé.
    """
    if teams_repository.check_name_exists(company_id, data.name):
        raise ValueError(
            "Une équipe portant ce nom existe déjà dans cette entreprise."
        )
    payload: Dict[str, Any] = {
        "company_id": company_id,
        "name": data.name,
        "description": data.description,
        "color": data.color or "#6366f1",
        "status": "active",
    }
    if data.manager_employee_id:
        mgr = teams_repository.get_employee_in_company(
            data.manager_employee_id, company_id
        )
        if not mgr:
            raise LookupError("Responsable d'équipe introuvable dans cette entreprise.")
        payload["manager_employee_id"] = data.manager_employee_id
    row = teams_repository.create_team(payload)
    return row


def update_team(team_id: str, data: TeamUpdate, company_id: str) -> dict:
    """
    1. Récupère team → LookupError si inexistant.
    2. Vérifie company_id → PermissionError si mismatch.
    3. Si name modifié : vérifie unicité (exclude_team_id=team_id).
    4. Update.
    """
    row = teams_repository.get_team_by_id(team_id)
    if not row:
        raise LookupError("Équipe introuvable.")
    if str(row.get("company_id")) != str(company_id):
        raise PermissionError("Accès non autorisé à cette équipe.")
    updates: Dict[str, Any] = {}
    if data.name is not None:
        if teams_repository.check_name_exists(company_id, data.name, team_id):
            raise ValueError(
                "Une équipe portant ce nom existe déjà dans cette entreprise."
            )
        updates["name"] = data.name
    if data.description is not None:
        updates["description"] = data.description
    if data.color is not None:
        updates["color"] = data.color
    if "manager_employee_id" in data.model_fields_set:
        mid = data.manager_employee_id
        if mid in (None, ""):
            updates["manager_employee_id"] = None
        else:
            mgr = teams_repository.get_employee_in_company(mid, company_id)
            if not mgr:
                raise LookupError(
                    "Responsable d'équipe introuvable dans cette entreprise."
                )
            updates["manager_employee_id"] = mid
    if not updates:
        return row
    return teams_repository.update_team(team_id, updates)


def archive_team(team_id: str, company_id: str) -> dict:
    """
    1. Récupère team → LookupError si inexistant.
    2. Vérifie company_id → PermissionError si mismatch.
    3. Désaffecte tous les salariés.
    4. Archive l'équipe.
    """
    row = teams_repository.get_team_by_id(team_id)
    if not row:
        raise LookupError("Équipe introuvable.")
    if str(row.get("company_id")) != str(company_id):
        raise PermissionError("Accès non autorisé à cette équipe.")
    teams_repository.unassign_team_employees(team_id)
    return teams_repository.archive_team(team_id)


def reactivate_team(team_id: str, company_id: str) -> dict:
    """
    1. Récupère team → LookupError si inexistant.
    2. Vérifie company_id → PermissionError si mismatch.
    3. Vérifie que status='archived' → ValueError sinon.
    4. Réactive.
    """
    row = teams_repository.get_team_by_id(team_id)
    if not row:
        raise LookupError("Équipe introuvable.")
    if str(row.get("company_id")) != str(company_id):
        raise PermissionError("Accès non autorisé à cette équipe.")
    if str(row.get("status") or "") != "archived":
        raise ValueError("Seule une équipe archivée peut être réactivée.")
    return teams_repository.reactivate_team(team_id)


def delete_team(team_id: str, company_id: str) -> bool:
    """
    1. Récupère team → LookupError si inexistant.
    2. Vérifie company_id → PermissionError si mismatch.
    3. Vérifie employee_count == 0 → ValueError sinon.
    4. Supprime.
    """
    row = teams_repository.get_team_by_id(team_id)
    if not row:
        raise LookupError("Équipe introuvable.")
    if str(row.get("company_id")) != str(company_id):
        raise PermissionError("Accès non autorisé à cette équipe.")
    n = teams_repository.get_employee_count(team_id)
    if n > 0:
        raise ValueError(
            "Cette équipe contient des salariés. Archivez-la plutôt que de la supprimer."
        )
    return teams_repository.delete_team(team_id)


def assign_employee_to_team(
    employee_id: str,
    team_id: Optional[str],
    company_id: str,
) -> dict:
    """
    1. Si team_id fourni : vérifie équipe existante, company et status active.
    2. Assign (ou NULL si team_id=None).
    3. Retourne l'employé mis à jour.
    """
    emp = teams_repository.get_employee_in_company(employee_id, company_id)
    if not emp:
        raise LookupError("Employé introuvable dans cette entreprise.")
    if team_id:
        team = teams_repository.get_team_by_id(team_id)
        if not team:
            raise LookupError("Équipe introuvable.")
        if str(team.get("company_id")) != str(company_id):
            raise PermissionError("Accès non autorisé à cette équipe.")
        if str(team.get("status") or "") != "active":
            raise ValueError("Impossible d'affecter un salarié à une équipe archivée.")
    return teams_repository.assign_employee_team(employee_id, team_id)
