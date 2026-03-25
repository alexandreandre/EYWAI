"""
Mappers : conversion entre lignes DB (Supabase) et schémas / DTOs.

Comportement identique aux constructions inline des anciens routers.
"""

from typing import Optional

from app.modules.users.schemas.responses import CompanyAccess, UserDetail


def row_to_company_access(
    acc: dict,
    company_data: Optional[dict] = None,
    role_override: Optional[str] = None,
) -> CompanyAccess:
    """Construit CompanyAccess depuis une ligne user_company_accesses + companies."""
    company = company_data or acc.get("companies") or {}
    return CompanyAccess(
        company_id=acc["company_id"],
        company_name=company.get("company_name", "Unknown"),
        role=role_override or acc.get("role", "collaborateur"),
        is_primary=acc.get("is_primary", False),
        siret=company.get("siret"),
        logo_url=company.get("logo_url"),
        logo_scale=company.get("logo_scale", 1.0),
        group_id=company.get("group_id"),
        group_name=company.get("group_name"),
        group_logo_url=company.get("group_logo_url"),
        group_logo_scale=company.get("group_logo_scale", 1.0),
    )


def row_to_company_access_super_admin(c: dict) -> CompanyAccess:
    """Construit CompanyAccess pour un super_admin (toutes les companies actives)."""
    groups = c.get("company_groups") or {}
    return CompanyAccess(
        company_id=c["id"],
        company_name=c["company_name"],
        role="super_admin",
        is_primary=False,
        siret=c.get("siret"),
        logo_url=c.get("logo_url"),
        logo_scale=c.get("logo_scale", 1.0),
        group_id=c.get("group_id"),
        group_name=groups.get("group_name"),
        group_logo_url=groups.get("logo_url"),
        group_logo_scale=groups.get("logo_scale", 1.0),
    )


def row_to_user_detail(
    row: dict,
    profile: dict,
    email: str,
    company_id: str,
    can_edit: bool,
) -> UserDetail:
    """Construit UserDetail depuis une ligne user_company_accesses + profile + email."""
    role_template = row.get("role_templates")
    return UserDetail(
        id=profile["id"],
        email=email,
        first_name=profile["first_name"],
        last_name=profile["last_name"],
        job_title=profile.get("job_title"),
        company_id=company_id,
        role=row["role"],
        role_template_name=role_template.get("name") if role_template else None,
        created_at=profile.get("created_at"),
        can_edit=can_edit,
    )
