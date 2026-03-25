"""
Entités du domaine employee_exits.

À migrer depuis les schémas et la logique actuelle de api/routers/employee_exits.py.
Pour l'instant : placeholders ; les entités métier (EmployeeExit, ExitDocument, ChecklistItem)
seront extraites lors de la migration.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict
from uuid import UUID


@dataclass
class EmployeeExitEntity:
    """
    Sortie de salarié (processus démission, rupture conventionnelle, licenciement, etc.).
    Source : table employee_exits, schéma EmployeeExit.
    """

    id: UUID
    company_id: UUID
    employee_id: UUID
    exit_type: str
    status: str
    exit_request_date: date
    last_working_day: date
    notice_period_days: int
    is_gross_misconduct: bool
    created_at: datetime
    updated_at: datetime
    # Champs optionnels (calculated_indemnities, exit_reason, etc.) : à compléter en migration
    extra: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


@dataclass
class ExitDocumentEntity:
    """
    Document lié à une sortie (uploadé ou généré).
    Source : table exit_documents.
    """

    id: UUID
    exit_id: UUID
    company_id: UUID
    document_type: str
    document_category: str  # 'uploaded' | 'generated'
    storage_path: str
    filename: str
    extra: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


@dataclass
class ChecklistItemEntity:
    """
    Item de checklist de sortie (restitution badge, matériel, etc.).
    Source : table exit_checklist_items.
    """

    id: UUID
    exit_id: UUID
    company_id: UUID
    item_code: str
    item_label: str
    item_category: str
    is_completed: bool
    is_required: bool
    display_order: int
    extra: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}
