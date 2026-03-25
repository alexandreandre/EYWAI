# app/modules/medical_follow_up/application/service.py
"""
Orchestration du module suivi médical : résolution company_id, gardes, accès repository et provider.

Ne contient pas d’accès DB direct ; utilise infrastructure (repository, provider) et
délègue le moteur de règles à l’obligation_engine du module (sans dépendance legacy).
"""

from typing import Any, List, Optional


def resolve_company_id_for_medical(current_user: Any) -> Optional[str]:
    """
    Retourne l’entreprise active pour le module suivi médical.
    active_company_id ou accessible_companies[0].company_id.
    """
    cid = getattr(current_user, "active_company_id", None)
    if cid:
        return str(cid)
    acc = getattr(current_user, "accessible_companies", None) or []
    if acc:
        return str(acc[0].company_id)
    return None


def get_obligation_repository():
    """Retourne une instance de MedicalObligationRepository (client Supabase injecté)."""
    from app.modules.medical_follow_up.infrastructure.database import get_supabase
    from app.modules.medical_follow_up.infrastructure.repository import (
        MedicalObligationRepository,
    )

    return MedicalObligationRepository(get_supabase())


def get_settings_provider():
    """Retourne une instance de CompanyMedicalSettingsProvider."""
    from app.modules.medical_follow_up.infrastructure.providers import (
        CompanyMedicalSettingsProvider,
    )

    return CompanyMedicalSettingsProvider()


def get_company_medical_setting(company_id: str) -> bool:
    """True si le module suivi médical est activé pour l’entreprise. Passe par le provider."""
    return get_settings_provider().is_enabled(company_id)


def compute_obligations_for_employee(company_id: str, employee_id: str) -> List[dict]:
    """
    Calcule et upsert les obligations de suivi médical pour un employé.
    Délègue au moteur du module (infrastructure.obligation_engine), sans dépendance legacy.
    """
    from app.modules.medical_follow_up.infrastructure.obligation_engine import (
        compute_obligations_for_employee as _compute,
    )

    return _compute(company_id, employee_id)


def ensure_module_enabled(current_user: Any) -> str:
    """
    Lève HTTPException 400 si pas d’entreprise active, 403 si module désactivé.
    Sinon retourne company_id (str).
    """
    from fastapi import HTTPException

    company_id = resolve_company_id_for_medical(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not get_company_medical_setting(company_id):
        raise HTTPException(
            status_code=403,
            detail="Module suivi médical non activé pour cette entreprise",
        )
    return company_id


def ensure_rh_access(current_user: Any, company_id: str) -> None:
    """Lève HTTPException 403 si pas d’accès RH sur l’entreprise."""
    from fastapi import HTTPException

    if not getattr(current_user, "has_rh_access_in_company", lambda _: False)(
        company_id
    ):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
