"""
Évaluation pure des permissions scopées (entreprise / équipes / exceptions).

Règles (fail-closed) :
1. Grant absent → refus
2. Exception deny → refus
3. Exception allow → accès
4. scope_mode company → accès
5. scope_mode teams + salarié dans une équipe listée → accès
6. sinon → refus

Aucun hardcode de noms d'équipes (MOI/MOD) ni de personnes : uniquement des UUID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Mapping, Sequence

ScopeMode = Literal["company", "teams", "none"]
TargetEffect = Literal["allow", "deny"]


@dataclass(frozen=True)
class PermissionGrantScope:
    """Périmètre d'un grant user_permissions pour une permission donnée."""

    permission_id: str
    permission_code: str
    company_id: str
    scope_mode: ScopeMode
    team_ids: frozenset[str] = field(default_factory=frozenset)
    # employee_id -> effect
    targets: Mapping[str, TargetEffect] = field(default_factory=dict)


@dataclass(frozen=True)
class EmployeeAccessContext:
    """Contexte salarié pour évaluer un accès."""

    employee_id: str
    company_id: str
    team_id: str | None = None


def normalize_scope_mode(raw: str | None) -> ScopeMode:
    mode = (raw or "company").strip().lower()
    if mode in ("company", "teams", "none"):
        return mode  # type: ignore[return-value]
    return "company"


def evaluate_employee_access(
    grant: PermissionGrantScope | None,
    employee: EmployeeAccessContext,
) -> bool:
    """
    Évalue si le grant autorise l'accès au salarié.

    Fail-closed : grant None → False.
    Refuse si company_id du salarié ≠ company_id du grant.
    """
    if grant is None:
        return False
    if employee.company_id != grant.company_id:
        return False

    effect = grant.targets.get(employee.employee_id)
    if effect == "deny":
        return False
    if effect == "allow":
        return True

    if grant.scope_mode == "company":
        return True
    if grant.scope_mode == "teams":
        if not employee.team_id:
            return False
        return employee.team_id in grant.team_ids
    # scope_mode == "none" : uniquement exceptions allow déjà traitées
    return False


def filter_allowed_employee_ids(
    grant: PermissionGrantScope | None,
    employees: Sequence[EmployeeAccessContext],
) -> list[str]:
    """Retourne les employee_id autorisés (ordre conservé, uniques)."""
    seen: set[str] = set()
    out: list[str] = []
    for emp in employees:
        if emp.employee_id in seen:
            continue
        if evaluate_employee_access(grant, emp):
            seen.add(emp.employee_id)
            out.append(emp.employee_id)
    return out


def build_grant_from_rows(
    *,
    permission_id: str,
    permission_code: str,
    company_id: str,
    scope_mode: str | None,
    team_ids: Iterable[str] | None = None,
    targets: Iterable[Mapping[str, str]] | None = None,
) -> PermissionGrantScope:
    """Construit un PermissionGrantScope à partir de lignes DB / DTO."""
    target_map: dict[str, TargetEffect] = {}
    for row in targets or []:
        emp_id = str(row.get("employee_id") or "")
        effect = str(row.get("effect") or "").strip().lower()
        if emp_id and effect in ("allow", "deny"):
            target_map[emp_id] = effect  # type: ignore[assignment]
    return PermissionGrantScope(
        permission_id=str(permission_id),
        permission_code=str(permission_code),
        company_id=str(company_id),
        scope_mode=normalize_scope_mode(scope_mode),
        team_ids=frozenset(str(t) for t in (team_ids or []) if t),
        targets=target_map,
    )
