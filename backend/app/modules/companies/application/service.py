"""
Orchestration partagée du module companies.

Résolution du company_id (contexte settings vs details).
Le calcul des KPIs est dans domain/kpis.py (règle pure).
"""

from typing import Any, Optional

from app.modules.companies.infrastructure import queries as companies_queries

# Réexport pour les tests (patch sur ce symbole) et rétrocompat.
get_company_id_from_profile = companies_queries.get_company_id_from_profile


def resolve_company_id_for_user(current_user: Any) -> Optional[str]:
    """
    Retourne l'entreprise active pour l'utilisateur (contexte settings).
    active_company_id ou accessible_companies[0].company_id.
    """
    cid = getattr(current_user, "active_company_id", None)
    if cid:
        return str(cid)
    acc = getattr(current_user, "accessible_companies", None) or []
    if acc:
        return str(acc[0].company_id)
    return None


def resolve_company_id_for_details(current_user: Any) -> Optional[str]:
    """
    Retourne le company_id du profil utilisateur (contexte GET /details).
    Comportement identique au routeur legacy (profiles.company_id).
    """
    # Appel via companies_queries pour que les patch unittest sur
    # app.modules.companies.infrastructure.queries.get_company_id_from_profile
    # s’appliquent (évite une référence figée sur l’alias get_company_id_from_profile).
    return companies_queries.get_company_id_from_profile(str(current_user.id))
