"""
Implémentations des repositories (accès DB Supabase).

Comportement identique aux appels inline des anciens routers.
"""

from typing import List, Optional

from app.core.database import supabase

from app.modules.users.domain.interfaces import (
    ICompanyRepository,
    IRoleTemplateRepository,
    IUserCompanyAccessRepository,
    IUserPermissionRepository,
    IUserRepository,
)


class SupabaseUserRepository(IUserRepository):
    """Table profiles."""

    def get_by_id(self, user_id: str) -> Optional[dict]:
        r = supabase.table("profiles").select("*").eq("id", user_id).execute()
        return r.data[0] if r.data else None

    def get_by_email(self, email: str) -> Optional[dict]:
        r = supabase.table("profiles").select("id, email").eq("email", email).execute()
        return r.data[0] if r.data else None

    def create(self, data: dict) -> None:
        supabase.table("profiles").insert(data).execute()

    def update(self, user_id: str, data: dict) -> None:
        supabase.table("profiles").update(data).eq("id", user_id).execute()


class SupabaseUserCompanyAccessRepository(IUserCompanyAccessRepository):
    """Table user_company_accesses."""

    def get_accesses_for_user(self, user_id: str) -> List[dict]:
        r = (
            supabase.table("user_company_accesses")
            .select(
                "company_id, role, is_primary, companies(id, company_name, siret, group_id)"
            )
            .eq("user_id", user_id)
            .execute()
        )
        return r.data or []

    def get_access_with_companies(self, user_id: str) -> List[dict]:
        return self.get_accesses_for_user(user_id)

    def get_by_user_and_company(self, user_id: str, company_id: str) -> Optional[dict]:
        r = (
            supabase.table("user_company_accesses")
            .select("*")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .execute()
        )
        return r.data[0] if r.data else None

    def get_by_user_and_company_with_template(
        self, user_id: str, company_id: str
    ) -> Optional[dict]:
        r = (
            supabase.table("user_company_accesses")
            .select("*, role_templates(*)")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .execute()
        )
        return r.data[0] if r.data else None

    def create(self, data: dict) -> dict:
        r = supabase.table("user_company_accesses").insert(data).execute()
        return r.data[0] if r.data else {}

    def update(self, user_id: str, company_id: str, data: dict) -> dict:
        r = (
            supabase.table("user_company_accesses")
            .update(data)
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .execute()
        )
        return r.data[0] if r.data else {}

    def delete(self, user_id: str, company_id: str) -> Optional[dict]:
        r = (
            supabase.table("user_company_accesses")
            .delete()
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .execute()
        )
        return r.data[0] if r.data else None

    def set_primary(self, user_id: str, company_id: str) -> None:
        supabase.table("user_company_accesses").update({"is_primary": False}).eq(
            "user_id", user_id
        ).execute()
        supabase.table("user_company_accesses").update({"is_primary": True}).eq(
            "user_id", user_id
        ).eq("company_id", company_id).execute()

    def count_admins(self, company_id: str) -> int:
        r = (
            supabase.table("user_company_accesses")
            .select("user_id")
            .eq("company_id", company_id)
            .eq("role", "admin")
            .execute()
        )
        return len(r.data) if r.data else 0


class SupabaseCompanyRepository(ICompanyRepository):
    """Table companies."""

    def get_active_with_groups(self) -> List[dict]:
        r = (
            supabase.table("companies")
            .select(
                "id, company_name, siret, logo_url, logo_scale, group_id, company_groups(group_name, logo_url, logo_scale)"
            )
            .eq("is_active", True)
            .execute()
        )
        return r.data or []

    def get_active_ids_and_names(self) -> List[dict]:
        r = supabase.table("companies").select("*").eq("is_active", True).execute()
        return r.data or []

    def get_name(self, company_id: str) -> Optional[str]:
        r = (
            supabase.table("companies")
            .select("company_name")
            .eq("id", company_id)
            .execute()
        )
        return r.data[0]["company_name"] if r.data else None


class SupabaseRoleTemplateRepository(IRoleTemplateRepository):
    """Tables role_templates, role_template_permissions."""

    _DEFAULT_NAMES = {
        "admin": "Administrateur",
        "rh": "Responsable RH",
        "collaborateur_rh": "Collaborateur RH",
        "collaborateur": "Collaborateur",
    }

    def get_default_system_template_id(self, base_role: str) -> Optional[str]:
        name = self._DEFAULT_NAMES.get(base_role)
        if not name:
            return None
        r = (
            supabase.table("role_templates")
            .select("id")
            .eq("name", name)
            .eq("is_system", True)
            .eq("is_active", True)
            .execute()
        )
        return r.data[0]["id"] if r.data else None

    def get_template_permission_ids(self, template_id: str) -> List[str]:
        r = (
            supabase.table("role_template_permissions")
            .select("permission_id")
            .eq("template_id", template_id)
            .execute()
        )
        return [row["permission_id"] for row in (r.data or [])]


class SupabaseUserPermissionRepository(IUserPermissionRepository):
    """Table user_permissions (+ role_template_permissions pour get)."""

    def has_any_rh_permission(self, user_id: str, company_id: str) -> bool:
        try:
            r = (
                supabase.table("user_permissions")
                .select("permissions(required_role, is_active)")
                .eq("user_id", str(user_id))
                .eq("company_id", str(company_id))
                .execute()
            )
            for row in r.data or []:
                perm = row.get("permissions")
                if perm and perm.get("is_active", False):
                    if perm.get("required_role") in ("rh", "admin"):
                        return True
            return False
        except Exception:
            return False

    def get_permission_ids(
        self, user_id: str, company_id: str, role_template_id: Optional[str] = None
    ) -> List[str]:
        r = (
            supabase.table("user_permissions")
            .select("permission_id")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .execute()
        )
        ids = set(row["permission_id"] for row in (r.data or []))
        if role_template_id:
            tr = (
                supabase.table("role_template_permissions")
                .select("permission_id")
                .eq("template_id", role_template_id)
                .execute()
            )
            for row in tr.data or []:
                ids.add(row["permission_id"])
        return list(ids)

    def copy_from_template(
        self, template_id: str, user_id: str, company_id: str, granted_by: str
    ) -> None:
        r = (
            supabase.table("role_template_permissions")
            .select("permission_id")
            .eq("template_id", template_id)
            .execute()
        )
        for row in r.data or []:
            supabase.table("user_permissions").upsert(
                {
                    "user_id": user_id,
                    "company_id": company_id,
                    "permission_id": row["permission_id"],
                    "granted_by": granted_by,
                },
                on_conflict="user_id,company_id,permission_id",
                ignore_duplicates=True,
            ).execute()

    def delete_for_user_company(self, user_id: str, company_id: str) -> None:
        supabase.table("user_permissions").delete().eq("user_id", user_id).eq(
            "company_id", company_id
        ).execute()

    def upsert(
        self, user_id: str, company_id: str, permission_id: str, granted_by: str
    ) -> None:
        supabase.table("user_permissions").upsert(
            {
                "user_id": user_id,
                "company_id": company_id,
                "permission_id": permission_id,
                "granted_by": granted_by,
            },
            on_conflict="user_id,company_id,permission_id",
            ignore_duplicates=True,
        ).execute()


# Instances partagées (pas de DI pour l'instant, comportement identique)
user_repository = SupabaseUserRepository()
user_company_access_repository = SupabaseUserCompanyAccessRepository()
company_repository = SupabaseCompanyRepository()
role_template_repository = SupabaseRoleTemplateRepository()
user_permission_repository = SupabaseUserPermissionRepository()
