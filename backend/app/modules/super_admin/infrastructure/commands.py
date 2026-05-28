"""
Commandes DB du module super_admin (infrastructure).

Écriture Supabase : companies, profiles, user_company_accesses ; Auth via providers.
Comportement identique à l'application ; pas de FastAPI.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.database import get_supabase_client

from app.modules.super_admin.infrastructure import providers

_log = logging.getLogger(__name__)

# Groupe plateforme unique — toute nouvelle entreprise y est rattachée automatiquement.
DEFAULT_PLATFORM_GROUP_NAME = "MAJI"


def _resolve_default_group_id(supabase: Any) -> Optional[str]:
    """Retourne l'id du groupe MAJI, ou le seul groupe existant."""
    by_name = (
        supabase.table("company_groups")
        .select("id")
        .ilike("group_name", DEFAULT_PLATFORM_GROUP_NAME)
        .limit(1)
        .execute()
    )
    if by_name.data:
        return str(by_name.data[0]["id"])
    all_groups = supabase.table("company_groups").select("id").limit(2).execute()
    if all_groups.data and len(all_groups.data) == 1:
        return str(all_groups.data[0]["id"])
    return None


def _attach_company_to_default_group(supabase: Any, company_id: str) -> Optional[str]:
    """Rattache l'entreprise au groupe MAJI (best effort)."""
    group_id = _resolve_default_group_id(supabase)
    if not group_id:
        _log.warning(
            "Groupe %s introuvable : entreprise %s non rattachée",
            DEFAULT_PLATFORM_GROUP_NAME,
            company_id,
        )
        return None
    updated = (
        supabase.table("companies")
        .update({"group_id": group_id})
        .eq("id", company_id)
        .execute()
    )
    if updated.data:
        return group_id
    return None


def create_company_with_admin(
    company_data: Dict[str, Any],
    _super_admin_row: Dict[str, Any],
) -> Dict[str, Any]:
    """Crée une entreprise et optionnellement un admin (Auth + profile + user_company_accesses)."""
    supabase = get_supabase_client()
    create_admin = bool(
        company_data.get("admin_email") and company_data.get("admin_password")
    )
    insert_payload = {
        "company_name": company_data["company_name"],
        "siret": company_data.get("siret"),
        "email": company_data.get("email"),
        "phone": company_data.get("phone"),
        "logo_url": company_data.get("logo_url"),
        "is_active": True,
    }
    new_company = supabase.table("companies").insert(insert_payload).execute()
    if not new_company.data:
        raise RuntimeError("Erreur lors de la création de l'entreprise")
    company_id = new_company.data[0]["id"]
    group_id = _attach_company_to_default_group(supabase, company_id)
    company_row = dict(new_company.data[0])
    if group_id:
        company_row["group_id"] = group_id
    admin_info = None
    if create_admin:
        try:
            auth_response = providers.create_user(
                company_data["admin_email"],
                company_data["admin_password"],
                {
                    "first_name": company_data.get("admin_first_name") or "",
                    "last_name": company_data.get("admin_last_name") or "",
                },
            )
            user_id = auth_response.user.id
        except Exception as auth_error:
            supabase.table("companies").delete().eq("id", company_id).execute()
            raise ValueError(
                f"Erreur lors de la création du compte admin: {str(auth_error)}"
            ) from auth_error
        try:
            profile_data = {
                "id": user_id,
                "company_id": company_id,
                "role": "admin",
                "first_name": company_data.get("admin_first_name") or "",
                "last_name": company_data.get("admin_last_name") or "",
            }
            supabase.table("profiles").insert(profile_data).execute()
            admin_info = {
                "id": user_id,
                "email": company_data["admin_email"],
                "first_name": company_data.get("admin_first_name") or "",
                "last_name": company_data.get("admin_last_name") or "",
            }
        except Exception as profile_error:
            supabase.table("companies").delete().eq("id", company_id).execute()
            providers.delete_user(user_id)
            raise ValueError(
                f"Erreur lors de la création du profil: {str(profile_error)}"
            ) from profile_error
    result = {"success": True, "company": company_row}
    if admin_info:
        result["admin"] = admin_info
    return result


def update_company(company_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Met à jour une entreprise."""
    supabase = get_supabase_client()
    if not update_data:
        raise ValueError("Aucune donnée à mettre à jour")
    result = (
        supabase.table("companies").update(update_data).eq("id", company_id).execute()
    )
    if not result.data:
        raise LookupError("Entreprise non trouvée")
    return {"success": True, "company": result.data[0]}


def delete_company_soft(company_id: str) -> Dict[str, Any]:
    """Désactive une entreprise (is_active=False)."""
    supabase = get_supabase_client()
    result = (
        supabase.table("companies")
        .update({"is_active": False})
        .eq("id", company_id)
        .execute()
    )
    if not result.data:
        raise LookupError("Entreprise non trouvée")
    return {"success": True, "message": "Entreprise désactivée"}


def delete_company_permanent(company_id: str) -> Dict[str, Any]:
    """Supprime définitivement une entreprise et toutes ses données."""
    supabase = get_supabase_client()
    company_check = (
        supabase.table("companies")
        .select("id, company_name")
        .eq("id", company_id)
        .execute()
    )
    if not company_check.data:
        raise LookupError("Entreprise non trouvée")
    company_name = company_check.data[0].get("company_name", "Inconnue")
    deletion_stats: Dict[str, int] = {}
    for table, key in [
        ("payslips", "payslips"),
        ("monthly_inputs", "monthly_inputs"),
        ("employee_schedules", "employee_schedules"),
        ("expense_reports", "expense_reports"),
        ("absence_requests", "absence_requests"),
        ("contracts", "contracts"),
        ("employees", "employees"),
        ("user_company_accesses", "user_company_accesses"),
    ]:
        r = supabase.table(table).delete().eq("company_id", company_id).execute()
        deletion_stats[key] = len(r.data) if r.data else 0
    try:
        r = (
            supabase.table("company_collective_agreements")
            .delete()
            .eq("company_id", company_id)
            .execute()
        )
        deletion_stats["company_collective_agreements"] = len(r.data) if r.data else 0
    except Exception:
        deletion_stats["company_collective_agreements"] = 0
    try:
        r = (
            supabase.table("payroll_config")
            .delete()
            .eq("company_id", company_id)
            .execute()
        )
        deletion_stats["payroll_config"] = len(r.data) if r.data else 0
    except Exception:
        deletion_stats["payroll_config"] = 0
    company_result = supabase.table("companies").delete().eq("id", company_id).execute()
    if not company_result.data:
        raise RuntimeError(
            "Impossible de supprimer l'entreprise après avoir supprimé ses dépendances"
        )
    return {
        "success": True,
        "message": f"Entreprise '{company_name}' et toutes ses données ont été supprimées définitivement",
        "deleted_company": {"id": company_id, "name": company_name},
        "deletion_statistics": deletion_stats,
        "total_records_deleted": sum(deletion_stats.values()) + 1,
    }


def create_company_user(company_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Crée un utilisateur pour une entreprise (Auth + profile + user_company_accesses)."""
    supabase = get_supabase_client()
    company = (
        supabase.table("companies")
        .select("id, company_name")
        .eq("id", company_id)
        .execute()
    )
    if not company.data:
        raise LookupError("Entreprise non trouvée")
    try:
        auth_response = providers.create_user(
            user_data["email"],
            user_data["password"],
            {
                "first_name": user_data.get("first_name", ""),
                "last_name": user_data.get("last_name", ""),
            },
        )
        user_id = auth_response.user.id
    except Exception as auth_error:
        raise ValueError(
            f"Erreur lors de la création du compte: {str(auth_error)}"
        ) from auth_error
    try:
        profile_data = {
            "id": user_id,
            "company_id": company_id,
            "role": user_data.get("role", "collaborateur"),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
        }
        profile_result = supabase.table("profiles").insert(profile_data).execute()
        access_data = {
            "user_id": user_id,
            "company_id": company_id,
            "role": user_data.get("role", "collaborateur"),
            "is_primary": True,
        }
        supabase.table("user_company_accesses").insert(access_data).execute()
        result_data = profile_result.data[0]
        result_data["email"] = user_data["email"]
        return {"success": True, "user": result_data}
    except Exception as profile_error:
        try:
            providers.delete_user(user_id)
        except Exception:
            pass
        raise ValueError(
            f"Erreur lors de la création du profil: {str(profile_error)}"
        ) from profile_error


def update_company_user(
    company_id: str,
    user_id: str,
    update_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Met à jour un utilisateur (profil, rôle, email)."""
    supabase = get_supabase_client()
    access = (
        supabase.table("user_company_accesses")
        .select("*")
        .eq("user_id", user_id)
        .eq("company_id", company_id)
        .execute()
    )
    if not access.data:
        raise LookupError("Utilisateur non trouvé pour cette entreprise")
    profile_updates: Dict[str, Any] = {}
    if "first_name" in update_data:
        profile_updates["first_name"] = update_data["first_name"]
    if "last_name" in update_data:
        profile_updates["last_name"] = update_data["last_name"]
    if profile_updates:
        supabase.table("profiles").update(profile_updates).eq("id", user_id).execute()
    if "role" in update_data:
        supabase.table("user_company_accesses").update(
            {"role": update_data["role"]}
        ).eq("user_id", user_id).eq("company_id", company_id).execute()
    if "email" in update_data:
        try:
            providers.update_user(user_id, {"email": update_data["email"]})
        except Exception as e:
            raise ValueError(
                f"Erreur lors de la mise à jour de l'email: {str(e)}"
            ) from e
    return {"success": True, "message": "Utilisateur mis à jour avec succès"}


def delete_company_user(company_id: str, user_id: str) -> Dict[str, Any]:
    """Retire l'accès utilisateur à l'entreprise ; supprime user si plus aucun accès."""
    supabase = get_supabase_client()
    access = (
        supabase.table("user_company_accesses")
        .select("*")
        .eq("user_id", user_id)
        .eq("company_id", company_id)
        .execute()
    )
    if not access.data:
        raise LookupError("Utilisateur non trouvé pour cette entreprise")
    supabase.table("user_company_accesses").delete().eq("user_id", user_id).eq(
        "company_id", company_id
    ).execute()
    remaining_accesses = (
        supabase.table("user_company_accesses")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if not remaining_accesses.data or len(remaining_accesses.data) == 0:
        supabase.table("profiles").delete().eq("id", user_id).execute()
        try:
            providers.delete_user(user_id)
        except Exception:
            pass
        message = "Utilisateur supprimé complètement (plus aucun accès)"
    else:
        message = f"Accès à l'entreprise supprimé (l'utilisateur a encore accès à {len(remaining_accesses.data)} entreprise(s))"
    return {"success": True, "message": message}
