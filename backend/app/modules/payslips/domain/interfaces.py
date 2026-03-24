"""
Ports (interfaces) du domaine payslips.

Aucune dépendance à FastAPI ni à la base. L'infrastructure implémente ces interfaces ;
l'application ne dépend que des abstractions.
"""
from __future__ import annotations

from typing import Any, Protocol


class IEmployeeStatutReader(Protocol):
    """Lecture du statut employé (pour décision forfait jour vs heures)."""

    def get_employee_statut(self, employee_id: str) -> str | None:
        """Retourne le statut de l'employé ou None."""
        ...


class IPayslipMetaReader(Protocol):
    """Lecture des métadonnées minimales d'un bulletin (contrôles d'accès)."""

    def get_payslip_meta(self, payslip_id: str) -> dict[str, Any] | None:
        """Retourne company_id, employee_id ou None si absent."""
        ...


class IPayslipGenerator(Protocol):
    """Génération d'un bulletin (heures ou forfait jour)."""

    def generate(
        self,
        employee_id: str,
        year: int,
        month: int,
    ) -> dict[str, Any]:
        """Lance la génération ; retourne {status, message, download_url} ou lève."""
        ...


class IPayslipEditor(Protocol):
    """Édition et restauration d'un bulletin existant."""

    def save_edited(
        self,
        payslip_id: str,
        new_payslip_data: dict[str, Any],
        changes_summary: str,
        current_user_id: str,
        current_user_name: str,
        pdf_notes: str | None = None,
        internal_note: str | None = None,
    ) -> dict[str, Any]:
        """Sauvegarde les modifications ; retourne {payslip, new_pdf_url}."""
        ...

    def restore_version(
        self,
        payslip_id: str,
        version: int,
        current_user_id: str,
        current_user_name: str,
    ) -> dict[str, Any]:
        """Restaure une version ; retourne {payslip, new_pdf_url}."""
        ...


class IPayslipRepository(Protocol):
    """Accès lecture/écriture aux bulletins (table payslips + storage)."""

    def get_by_id(self, payslip_id: str) -> dict[str, Any] | None:
        """Récupère un bulletin par id."""
        ...

    def list_by_employee(self, employee_id: str) -> list[dict[str, Any]]:
        """Liste les bulletins d'un employé."""
        ...

    def delete(self, payslip_id: str) -> None:
        """Supprime le bulletin (BDD + fichier storage) et déclenche recalc COR si besoin."""
        ...


class IDebugStorageInfoProvider(Protocol):
    """Fournit les métadonnées Storage pour diagnostic (debug)."""

    def get_debug_storage_info(
        self,
        employee_id: str,
        year: int,
        month: int,
    ) -> dict[str, Any]:
        """Retourne les infos API Storage pour le chemin bulletin (ou lève si employé absent)."""
        ...
