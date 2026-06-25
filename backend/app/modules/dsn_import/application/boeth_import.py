"""Import BOETH depuis la DSN (S21.G00.40.072)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.modules.dsn_import.domain.model import ContratBlock
from app.modules.dsn_import.domain.rubriques import R_S21_CTR_STATUT_BOETH
from app.modules.oeth_settings.application.commands import save_employee_boeth
from app.modules.oeth_settings.application.queries import _label_boeth
from app.modules.oeth_settings.domain.constants import BOETH_CODES
from app.modules.oeth_settings.infrastructure.boeth_repository import boeth_profiles_repository
from app.modules.oeth_settings.infrastructure.headcount_service import load_oeth_config
from app.modules.oeth_settings.schemas.requests import EmployeeBoethUpdate


def normalize_boeth_code(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value.isdigit():
        value = value.zfill(2)
    if value in BOETH_CODES:
        return value
    return None


def extract_boeth_from_contrat(
    contrat: ContratBlock,
    *,
    valid_from: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    code = normalize_boeth_code(contrat.rubriques.get(R_S21_CTR_STATUT_BOETH))
    if not code:
        return None
    return {
        "boeth_code": code,
        "valid_from": valid_from or date.today().isoformat(),
        "notes": "Import DSN",
    }


def boeth_preview_columns(boeth: Dict[str, Any]) -> Dict[str, str]:
    config = load_oeth_config()
    label = _label_boeth(boeth.get("boeth_code"), config)
    return {
        "boeth_code": str(boeth["boeth_code"]),
        "boeth_label": label or str(boeth["boeth_code"]),
    }


def append_boeth_review_conflict(item: Dict[str, Any], company_id: Optional[str]) -> None:
    """Marque l'item en revue si le BOETH DSN diffère du profil actif."""
    payload = item.get("mapped_payload") or {}
    boeth = payload.get("_boeth")
    emp_id = item.get("existing_employee_id")
    if not boeth or not emp_id:
        return
    existing = boeth_profiles_repository.get_active_by_employee(emp_id)
    if not existing:
        return
    if company_id and str(existing.get("company_id")) != str(company_id):
        return
    dsn_code = str(boeth.get("boeth_code"))
    profile_code = str(existing.get("boeth_code"))
    if dsn_code == profile_code:
        return
    reasons = list(item.get("review_reasons") or [])
    if "boeth_conflict" not in reasons:
        reasons.append("boeth_conflict")
    item["review_reasons"] = reasons
    item["needs_review"] = True
    item["boeth_conflict"] = {
        "dsn_code": dsn_code,
        "profile_code": profile_code,
    }


def apply_dsn_boeth_on_commit(
    company_id: str,
    employee_id: str,
    payload: Dict[str, Any],
) -> Optional[str]:
    """Applique le BOETH DSN si pas de conflit. Retourne un avertissement sinon."""
    boeth = payload.get("_boeth")
    if not boeth:
        return None
    dsn_code = str(boeth.get("boeth_code"))
    existing = boeth_profiles_repository.get_active_by_employee(employee_id)
    if existing:
        if str(existing.get("boeth_code")) == dsn_code:
            return None
        return (
            f"Statut BOETH conservé — conflit DSN ({dsn_code}) "
            f"vs fiche ({existing.get('boeth_code')})."
        )
    save_employee_boeth(
        company_id,
        employee_id,
        EmployeeBoethUpdate(
            boeth_code=dsn_code,
            valid_from=boeth["valid_from"],
            notes=boeth.get("notes"),
        ),
    )
    return None
