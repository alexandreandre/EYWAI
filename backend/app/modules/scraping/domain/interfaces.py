"""
Interfaces (ports) du domaine scraping.

L'infrastructure implémente ces abstractions ; l'application ne dépend pas des détails.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class IScrapingRepository(Protocol):
    """Port pour la persistance des sources, jobs, schedules, alertes."""

    def get_scraping_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques globales (RPC get_scraping_stats)."""
        ...

    def get_source_by_id(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une source par id."""
        ...

    def get_source_by_key(self, source_key: str) -> Optional[Dict[str, Any]]:
        """Récupère une source par source_key."""
        ...

    def list_sources(
        self,
        source_type: Optional[str] = None,
        is_critical: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Liste les sources avec filtres optionnels."""
        ...

    def list_jobs(
        self,
        source_id: Optional[str] = None,
        status: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Liste les jobs avec filtres et pagination."""
        ...

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un job par id."""
        ...

    def create_job(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée un job et retourne la ligne créée."""
        ...

    def update_job(self, job_id: str, data: Dict[str, Any]) -> None:
        """Met à jour un job."""
        ...

    def create_alert(self, data: Dict[str, Any]) -> None:
        """Crée une alerte."""
        ...

    def list_schedules(
        self,
        is_enabled: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Liste les planifications."""
        ...

    def create_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une planification."""
        ...

    def update_schedule(self, schedule_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Met à jour une planification."""
        ...

    def delete_schedule(self, schedule_id: str) -> bool:
        """Supprime une planification."""
        ...

    def list_alerts(
        self,
        is_read: Optional[bool] = None,
        is_resolved: Optional[bool] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Liste les alertes avec filtres."""
        ...

    def mark_alert_read(self, alert_id: str) -> bool:
        """Marque une alerte comme lue."""
        ...

    def resolve_alert(self, alert_id: str, data: Dict[str, Any]) -> bool:
        """Résout une alerte."""
        ...


class IScraperRunner(Protocol):
    """Port pour l'exécution d'un script de scraping (subprocess)."""

    def get_script_path(
        self,
        source_data: Dict[str, Any],
        scraper_name: Optional[str] = None,
        use_orchestrator: bool = True,
    ) -> tuple[str, str]:
        """
        Retourne (chemin_absolu_script, script_type).
        script_type = "orchestrator" | "single_scraper".
        """
        ...

    def run(
        self,
        source_data: Dict[str, Any],
        scraper_name: Optional[str] = None,
        use_orchestrator: bool = True,
        triggered_by: str = "",
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exécute le script et met à jour le job (logs, statut, alerte si échec).
        Retourne dict avec job_id, success, duration_ms, error_message, data_extracted.
        """
        ...
