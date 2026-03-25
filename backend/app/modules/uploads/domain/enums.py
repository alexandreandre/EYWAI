"""
Types d'entité pour les uploads de logos.

À migrer depuis api/routers/uploads.py (entity_type: 'company' | 'group').
"""

from enum import Enum


class EntityType(str, Enum):
    """Entité concernée par l'upload (company ou group)."""

    COMPANY = "company"
    GROUP = "group"
