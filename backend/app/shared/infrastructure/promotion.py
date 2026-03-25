"""
Promotions et accès RH employé.
Délégation au module promotions (repository / queries), sans passer par services/.
"""

from typing import Any, Dict, List, Optional


def _coerce_filter(value: Any) -> Any:
    """Accepte str ou enum (legacy) pour status / promotion_type."""
    if value is None:
        return None
    return getattr(value, "value", value)


def get_promotions(
    company_id: str,
    employee_id: Optional[str] = None,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    """Liste les promotions ; retourne des dict pour découplage avec le module employees."""
    from app.modules.promotions.infrastructure.queries import list_promotions

    items = list_promotions(
        company_id=company_id,
        year=kwargs.get("year"),
        status=_coerce_filter(kwargs.get("status")),
        promotion_type=_coerce_filter(kwargs.get("promotion_type")),
        employee_id=employee_id,
        search=kwargs.get("search"),
        limit=kwargs.get("limit"),
        offset=kwargs.get("offset"),
    )
    return [r.model_dump() if hasattr(r, "model_dump") else r for r in items]


def get_employee_rh_access(employee_id: str, company_id: str) -> Dict[str, Any]:
    """Accès RH courant d’un employé ; retourne un dict."""
    from app.modules.promotions.infrastructure.queries import (
        get_employee_rh_access as _impl,
    )

    obj = _impl(employee_id=employee_id, company_id=company_id)
    return obj.model_dump() if hasattr(obj, "model_dump") else obj
