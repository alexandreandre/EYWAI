"""
Lecture / résolution des grants scopés (user_permissions + team scopes + targets).
"""

from __future__ import annotations

from typing import Any, Sequence

from app.core.database import supabase
from app.modules.access_control.domain.scopes import (
    EmployeeAccessContext,
    PermissionGrantScope,
    build_grant_from_rows,
    evaluate_employee_access,
    filter_allowed_employee_ids,
)


class SupabaseScopedPermissionRepository:
    """Charge et remplace les grants avec leurs périmètres."""

    def get_grant(
        self,
        user_id: str,
        company_id: str,
        permission_code: str,
    ) -> PermissionGrantScope | None:
        try:
            result = (
                supabase.table("user_permissions")
                .select(
                    "id, company_id, permission_id, scope_mode, "
                    "permissions(code, is_active)"
                )
                .eq("user_id", str(user_id))
                .eq("company_id", str(company_id))
                .execute()
            )
        except Exception:
            return None

        grant_row: dict[str, Any] | None = None
        for row in result.data or []:
            perm = row.get("permissions") or {}
            if perm.get("code") == permission_code and perm.get("is_active", False):
                grant_row = row
                break
        if not grant_row:
            return None

        up_id = str(grant_row["id"])
        team_ids = self._load_team_ids(up_id)
        targets = self._load_targets(up_id)
        return build_grant_from_rows(
            permission_id=str(grant_row["permission_id"]),
            permission_code=permission_code,
            company_id=str(grant_row["company_id"]),
            scope_mode=grant_row.get("scope_mode"),
            team_ids=team_ids,
            targets=targets,
        )

    def list_grants_for_user_company(
        self, user_id: str, company_id: str
    ) -> list[dict[str, Any]]:
        """Liste les grants avec scopes pour l'UI (détail éditable)."""
        result = (
            supabase.table("user_permissions")
            .select(
                "id, permission_id, scope_mode, "
                "permissions(code, label, is_active)"
            )
            .eq("user_id", str(user_id))
            .eq("company_id", str(company_id))
            .execute()
        )
        out: list[dict[str, Any]] = []
        for row in result.data or []:
            perm = row.get("permissions") or {}
            if not perm.get("is_active", True):
                continue
            up_id = str(row["id"])
            out.append(
                {
                    "user_permission_id": up_id,
                    "permission_id": str(row["permission_id"]),
                    "permission_code": perm.get("code"),
                    "permission_label": perm.get("label"),
                    "scope_mode": row.get("scope_mode") or "company",
                    "team_ids": self._load_team_ids(up_id),
                    "targets": self._load_targets(up_id),
                }
            )
        return out

    def replace_grants_atomic(
        self,
        *,
        user_id: str,
        company_id: str,
        granted_by: str,
        grants: Sequence[dict[str, Any]],
    ) -> None:
        """
        Remplace atomiquement (best-effort séquentiel) permissions + scopes.

        Chaque grant : {permission_id, scope_mode, team_ids?, targets?}
        targets : [{employee_id, effect}]
        Pas de fenêtre avec scope company par défaut : scope_mode obligatoire
        (défaut explicite 'company' uniquement si fourni par l'appelant).
        """
        # Supprimer d'abord (CASCADE sur team_scopes / targets)
        supabase.table("user_permissions").delete().eq("user_id", str(user_id)).eq(
            "company_id", str(company_id)
        ).execute()

        for g in grants:
            permission_id = str(g["permission_id"])
            scope_mode = str(g.get("scope_mode") or "company").strip().lower()
            if scope_mode not in ("company", "teams", "none"):
                scope_mode = "company"
            inserted = (
                supabase.table("user_permissions")
                .insert(
                    {
                        "user_id": str(user_id),
                        "company_id": str(company_id),
                        "permission_id": permission_id,
                        "granted_by": str(granted_by),
                        "scope_mode": scope_mode,
                    }
                )
                .execute()
            )
            rows = inserted.data or []
            if not rows:
                # Relecture si insert ne retourne pas la ligne
                refetch = (
                    supabase.table("user_permissions")
                    .select("id")
                    .eq("user_id", str(user_id))
                    .eq("company_id", str(company_id))
                    .eq("permission_id", permission_id)
                    .limit(1)
                    .execute()
                )
                rows = refetch.data or []
            if not rows:
                continue
            up_id = str(rows[0]["id"])

            if scope_mode == "teams":
                for team_id in g.get("team_ids") or []:
                    supabase.table("user_permission_team_scopes").insert(
                        {
                            "user_permission_id": up_id,
                            "company_id": str(company_id),
                            "team_id": str(team_id),
                        }
                    ).execute()

            for target in g.get("targets") or []:
                emp_id = target.get("employee_id")
                effect = str(target.get("effect") or "").strip().lower()
                if not emp_id or effect not in ("allow", "deny"):
                    continue
                supabase.table("user_permission_targets").insert(
                    {
                        "user_permission_id": up_id,
                        "company_id": str(company_id),
                        "employee_id": str(emp_id),
                        "effect": effect,
                    }
                ).execute()

    def load_employee_contexts(
        self, company_id: str, employee_ids: Sequence[str] | None = None
    ) -> list[EmployeeAccessContext]:
        q = (
            supabase.table("employees")
            .select("id, company_id, team_id")
            .eq("company_id", str(company_id))
        )
        if employee_ids is not None:
            ids = [str(e) for e in employee_ids]
            if not ids:
                return []
            q = q.in_("id", ids)
        result = q.execute()
        return [
            EmployeeAccessContext(
                employee_id=str(row["id"]),
                company_id=str(row["company_id"]),
                team_id=str(row["team_id"]) if row.get("team_id") else None,
            )
            for row in (result.data or [])
        ]

    def _load_team_ids(self, user_permission_id: str) -> list[str]:
        try:
            r = (
                supabase.table("user_permission_team_scopes")
                .select("team_id")
                .eq("user_permission_id", str(user_permission_id))
                .execute()
            )
            return [str(row["team_id"]) for row in (r.data or []) if row.get("team_id")]
        except Exception:
            return []

    def _load_targets(self, user_permission_id: str) -> list[dict[str, str]]:
        try:
            r = (
                supabase.table("user_permission_targets")
                .select("employee_id, effect")
                .eq("user_permission_id", str(user_permission_id))
                .execute()
            )
            return [
                {
                    "employee_id": str(row["employee_id"]),
                    "effect": str(row["effect"]),
                }
                for row in (r.data or [])
                if row.get("employee_id") and row.get("effect")
            ]
        except Exception:
            return []


scoped_permission_repository = SupabaseScopedPermissionRepository()


def user_can_access_employee(
    user_id: str,
    company_id: str,
    permission_code: str,
    employee_id: str,
    *,
    team_id: str | None = None,
    repo: SupabaseScopedPermissionRepository | None = None,
) -> bool:
    """
    True si l'utilisateur a le grant et le salarié est dans le périmètre.

    Si team_id n'est pas fourni, charge le salarié en base.
    """
    repository = repo or scoped_permission_repository
    grant = repository.get_grant(user_id, company_id, permission_code)
    if grant is None:
        return False
    if team_id is not None:
        emp = EmployeeAccessContext(
            employee_id=str(employee_id),
            company_id=str(company_id),
            team_id=str(team_id) if team_id else None,
        )
        return evaluate_employee_access(grant, emp)
    contexts = repository.load_employee_contexts(company_id, [str(employee_id)])
    if not contexts:
        return False
    return evaluate_employee_access(grant, contexts[0])


def filter_allowed_employee_ids_for_user(
    user_id: str,
    company_id: str,
    permission_code: str,
    employee_ids: Sequence[str] | None = None,
    *,
    repo: SupabaseScopedPermissionRepository | None = None,
) -> list[str]:
    """Filtre une population (ou toute l'entreprise) selon le grant scopé."""
    repository = repo or scoped_permission_repository
    grant = repository.get_grant(user_id, company_id, permission_code)
    if grant is None:
        return []
    contexts = repository.load_employee_contexts(company_id, employee_ids)
    return filter_allowed_employee_ids(grant, contexts)
