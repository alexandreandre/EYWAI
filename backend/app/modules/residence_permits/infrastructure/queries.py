"""
Requêtes Supabase pour le module residence_permits.

Lecture des employés soumis au titre de séjour (liste page RH).
Client via app.core.database uniquement (aucun import legacy).
"""

from __future__ import annotations

from typing import List

from app.core.database import get_supabase_client


def _get_client():
    return get_supabase_client()


def fetch_employees_for_residence_permits_list(company_id: str) -> List[dict]:
    """
    Employés soumis au titre de séjour, actifs ou en_sortie, pour la liste titres de séjour.
    Colonnes : id, first_name, last_name, is_subject_to_residence_permit,
    residence_permit_expiry_date, residence_permit_type, residence_permit_number, employment_status.
    """
    client = _get_client()
    response = (
        client.table("employees")
        .select(
            "id, first_name, last_name, is_subject_to_residence_permit, "
            "residence_permit_expiry_date, residence_permit_type, residence_permit_number, employment_status"
        )
        .eq("company_id", company_id)
        .eq("is_subject_to_residence_permit", True)
        .in_("employment_status", ["actif", "en_sortie"])
        .order("last_name")
        .execute()
    )
    return list(response.data or [])


EXPORT_COLUMNS = (
    "id, first_name, last_name, matricule, job_title, hire_date, nationalite, "
    "is_subject_to_residence_permit, residence_permit_expiry_date, "
    "residence_permit_type, residence_permit_number, employment_status"
)


def fetch_employees_for_residence_permits_export(
    company_id: str, employee_ids: List[str]
) -> List[dict]:
    """
    Employés désignés par le navigateur, bornés à l'entreprise active.

    Les identifiants viennent du client : ils désignent, ils n'autorisent pas. Les
    trois filtres de la route liste sont donc réappliqués ici, `company_id` en tête.
    Un identifiant hors périmètre disparaît simplement du résultat.
    """
    if not employee_ids:
        return []
    client = _get_client()
    response = (
        client.table("employees")
        .select(EXPORT_COLUMNS)
        .eq("company_id", company_id)
        .eq("is_subject_to_residence_permit", True)
        .in_("employment_status", ["actif", "en_sortie"])
        .in_("id", list(employee_ids))
        .execute()
    )
    return list(response.data or [])
