"""
Couche application du module promotions.

Expose les commandes et queries pour le router. Wrappers legacy pour l'instant.
"""

from __future__ import annotations

from app.modules.promotions.application.commands import (
    approve_promotion_cmd,
    create_promotion_cmd,
    delete_promotion_cmd,
    mark_effective_promotion_cmd,
    reject_promotion_cmd,
    submit_promotion_cmd,
    update_promotion_cmd,
)
from app.modules.promotions.application.queries import (
    get_employee_rh_access_query,
    get_promotion_by_id_query,
    get_promotion_document_stream_query,
    get_promotion_stats_query,
    list_promotions_query,
)

__all__ = [
    "create_promotion_cmd",
    "update_promotion_cmd",
    "submit_promotion_cmd",
    "approve_promotion_cmd",
    "reject_promotion_cmd",
    "mark_effective_promotion_cmd",
    "delete_promotion_cmd",
    "list_promotions_query",
    "get_promotion_by_id_query",
    "get_promotion_stats_query",
    "get_employee_rh_access_query",
    "get_promotion_document_stream_query",
]
