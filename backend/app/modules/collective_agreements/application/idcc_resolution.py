"""
Résolution canonique IDCC + minima conventionnels (paie réelle et simulation).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.core.database import get_supabase_client
from app.modules.collective_agreements.domain.rules import idcc_variants
from app.modules.collective_agreements.rules.constants import SMH_NATIONAL_IDCC
from app.modules.collective_agreements.rules.repository import CCRulesRepository
from app.modules.collective_agreements.rules.resolver import resolve_salaires_minima
from app.modules.payroll.engine.baremes_loader import ensure_dict


def _parse_json_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def get_idcc_for_agreement(agreement_id: str, supabase_client: Any = None) -> Optional[str]:
    """Lit l'IDCC depuis collective_agreements_catalog."""
    if not agreement_id:
        return None
    client = supabase_client or get_supabase_client()
    try:
        response = (
            client.table("collective_agreements_catalog")
            .select("idcc")
            .eq("id", agreement_id)
            .maybe_single()
            .execute()
        )
        if response.data and response.data.get("idcc"):
            return str(response.data["idcc"]).strip()
    except Exception:
        return None
    return None


def _first_company_agreement_id(company_id: str, supabase_client: Any) -> Optional[str]:
    if not company_id:
        return None
    try:
        response = (
            supabase_client.table("company_collective_agreements")
            .select("collective_agreement_id")
            .eq("company_id", company_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            return rows[0].get("collective_agreement_id")
    except Exception:
        return None
    return None


def resolve_employee_idcc(
    employee_row: Dict[str, Any],
    company_row: Dict[str, Any],
    *,
    supabase_client: Any = None,
) -> Optional[str]:
    """
    Priorité : CC fiche salarié → première CC assignée à l'entreprise → companies.idcc.
    """
    client = supabase_client or get_supabase_client()
    agreement_id = employee_row.get("collective_agreement_id")
    if not agreement_id:
        agreement_id = _first_company_agreement_id(
            str(company_row.get("id") or employee_row.get("company_id") or ""),
            client,
        )
    if agreement_id:
        idcc = get_idcc_for_agreement(str(agreement_id), client)
        if idcc:
            return idcc
    company_idcc = company_row.get("idcc")
    if company_idcc:
        return str(company_idcc).strip()
    return None


def build_convention_collective_payload(
    employee_row: Dict[str, Any],
    company_row: Dict[str, Any],
    *,
    supabase_client: Any = None,
) -> Dict[str, Any]:
    """Bloc convention_collective pour contrat.json / payload simulation."""
    idcc = resolve_employee_idcc(employee_row, company_row, supabase_client=supabase_client)
    if not idcc:
        return {}
    libelle = (
        company_row.get("collective_agreement")
        or company_row.get("collective_agreement_name")
        or company_row.get("ccn_name")
        or ""
    )
    return {"idcc": idcc, "libelle": str(libelle).strip()}


def _fetch_rules_for_idcc(idcc: str, supabase_client: Any = None) -> Dict[str, Any]:
    repo = CCRulesRepository(supabase_client)
    for variant in idcc_variants(idcc):
        row = repo.get_rules_by_idcc(variant)
        if row and row.get("rules"):
            return ensure_dict(row.get("rules"))
    return {}


def get_salary_minima_for_idcc(
    idcc: str,
    *,
    code_postal: Optional[str] = None,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    """Grille de minima applicable pour un IDCC (résolution géographique incluse)."""
    rules = _fetch_rules_for_idcc(idcc, supabase_client)
    if not rules:
        return []
    minima = resolve_salaires_minima(rules, code_postal=code_postal)
    return [m for m in minima if isinstance(m, dict)]


def get_salary_minima_for_agreement(
    agreement_id: str,
    *,
    code_postal: Optional[str] = None,
    supabase_client: Any = None,
) -> List[Dict[str, Any]]:
    idcc = get_idcc_for_agreement(agreement_id, supabase_client)
    if not idcc:
        return []
    return get_salary_minima_for_idcc(
        idcc, code_postal=code_postal, supabase_client=supabase_client
    )


def _is_smh_national_idcc(idcc: str | None) -> bool:
    if not idcc:
        return False
    normalized = idcc.strip()
    if normalized in SMH_NATIONAL_IDCC:
        return True
    stripped = normalized.lstrip("0") or "0"
    return stripped in {x.lstrip("0") for x in SMH_NATIONAL_IDCC}


def _classification_lookup_keys(
    classification: Dict[str, Any],
    *,
    idcc: str | None = None,
) -> List[float]:
    """
    Clés de recherche dans la grille CC.

    Métallurgie SMH (3248) : la grille est indexée par classe d'emploi (1-18),
    le coefficient de position (ex. 710) ne correspond pas aux minima SMH.
    """
    if _is_smh_national_idcc(idcc):
        field_order = ("classe_emploi", "classe", "coefficient")
    else:
        field_order = ("coefficient", "classe_emploi", "classe")

    keys: List[float] = []
    seen: set[float] = set()
    for field in field_order:
        raw = classification.get(field)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if _is_smh_national_idcc(idcc) and field == "coefficient" and value > 18:
            continue
        if value not in seen:
            keys.append(value)
            seen.add(value)
    return keys


def resolve_minimum_for_classification(
    minima: List[Dict[str, Any]],
    classification: Dict[str, Any],
    *,
    idcc: str | None = None,
) -> Optional[Dict[str, Any]]:
    """Retourne la ligne de minimum correspondant à la classification."""
    if not minima or not classification:
        return None
    lookup = _classification_lookup_keys(classification, idcc=idcc)
    if not lookup:
        return None
    for key in lookup:
        for row in minima:
            if not isinstance(row, dict):
                continue
            try:
                if float(row.get("coefficient")) == key:
                    return row
            except (TypeError, ValueError):
                continue
    return None


def resolve_minimum_salary_value(
    agreement_id: str,
    classification: Dict[str, Any],
    *,
    code_postal: Optional[str] = None,
    supabase_client: Any = None,
) -> Optional[float]:
    """Montant mensuel minimum conventionnel pour un grade donné."""
    minima = get_salary_minima_for_agreement(
        agreement_id,
        code_postal=code_postal,
        supabase_client=supabase_client,
    )
    row = resolve_minimum_for_classification(minima, classification)
    if not row:
        return None
    try:
        return float(row.get("valeur") or 0)
    except (TypeError, ValueError):
        return None


def company_code_postal(company_row: Dict[str, Any]) -> Optional[str]:
    cp = company_row.get("adresse_code_postal")
    if cp:
        return str(cp).strip()
    address = company_row.get("address") or company_row.get("headquarters_address")
    if isinstance(address, dict):
        cp = address.get("code_postal")
        if cp:
            return str(cp).strip()
    return None
