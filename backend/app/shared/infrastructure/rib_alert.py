"""
Alertes RIB (normalisation IBAN, callbacks mise à jour / soumission).

Façade stable pour les modules app/* : délègue à app.shared.utils.iban et au module rib_alerts.
"""
from typing import Any, Dict, List


def normalize_iban(iban: str) -> str:
    """Normalise un IBAN pour comparaison (sans espaces, tirets, majuscules)."""
    from app.shared.utils.iban import normalize_iban as _impl
    return _impl(iban)


def on_rib_updated(
    company_id: str,
    employee_id: str,
    old_iban: str,
    new_iban: str,
    employee_name: str,
) -> None:
    """Crée une alerte rib_modified si l'IBAN a réellement changé."""
    from app.modules.rib_alerts.infrastructure.providers import on_rib_updated as _impl
    return _impl(company_id, employee_id, old_iban, new_iban, employee_name)


def on_rib_submitted(
    company_id: str,
    employee_id: str,
    new_iban: str,
    employee_name: str,
) -> List[Dict[str, Any]]:
    """Détecte les doublons d'IBAN et crée une alerte rib_duplicate le cas échéant."""
    from app.modules.rib_alerts.infrastructure.providers import on_rib_submitted as _impl
    return _impl(company_id, employee_id, new_iban, employee_name)
