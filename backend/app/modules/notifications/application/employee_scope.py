"""Résolution employé pour les notifications — délégation vers l'API partagée."""

from __future__ import annotations

from app.shared.employee_resolution import resolve_employee_id_for_user_account

# Alias conservé pour le module notifications (pas de réimplémentation Supabase).
resolve_employee_id_for_notifications = resolve_employee_id_for_user_account

__all__ = ["resolve_employee_id_for_notifications"]
