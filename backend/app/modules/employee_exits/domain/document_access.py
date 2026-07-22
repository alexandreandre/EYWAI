"""
Règles d'accès au dossier documents pendant un départ.

Le RH conserve l'accès au dossier complet du collaborateur pendant la procédure
de sortie, jusqu'au dernier jour travaillé inclus.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def rh_can_view_employee_documents(
    employee: Dict[str, Any],
    *,
    reference_date: Optional[date] = None,
) -> bool:
    """
    Indique si le RH peut consulter le dossier documents du collaborateur.

    - Actif / onboarding : oui
    - En sortie : oui jusqu'au dernier jour travaillé inclus
    - Parti : oui si la date de référence est antérieure ou égale au dernier jour travaillé
    """
    status = str(employee.get("employment_status") or "actif").lower()
    if status not in ("en_sortie", "parti"):
        return True

    last_day = _parse_date(employee.get("exit_last_working_day"))
    if last_day is None:
        return True

    ref = reference_date or date.today()
    return ref <= last_day


def rh_should_list_in_documents_explorer(
    employee: Dict[str, Any],
    *,
    reference_date: Optional[date] = None,
) -> bool:
    """
    Collaborateurs listés dans l'explorateur documents entreprise (/documents).

    Les dossiers archivés (statut « parti ») et les sorties après le dernier jour
    travaillé n'y apparaissent plus ; le détail reste accessible depuis la fiche RH.
    """
    status = str(employee.get("employment_status") or "actif").lower()
    if status == "parti":
        return False
    return rh_can_view_employee_documents(employee, reference_date=reference_date)


def rh_documents_access_message(
    employee: Dict[str, Any],
    *,
    reference_date: Optional[date] = None,
) -> Optional[str]:
    """Message informatif pour l'interface RH, ou None si hors contexte de départ."""
    status = str(employee.get("employment_status") or "actif").lower()
    if status not in ("en_sortie", "parti"):
        return None

    last_day = _parse_date(employee.get("exit_last_working_day"))
    if not last_day:
        return (
            "Ce collaborateur est en cours de départ. "
            "Vous pouvez consulter l'ensemble de son dossier documents."
        )

    formatted = last_day.strftime("%d/%m/%Y")
    if rh_can_view_employee_documents(employee, reference_date=reference_date):
        return (
            f"Ce collaborateur est en cours de départ. "
            f"Vous pouvez consulter son dossier documents jusqu'au {formatted} inclus."
        )
    return (
        f"Le dernier jour travaillé de ce collaborateur était le {formatted}. "
        "Le dossier reste consultable à des fins d'archivage RH."
    )
