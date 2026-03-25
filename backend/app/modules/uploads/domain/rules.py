"""
Règles métier pures pour les uploads de logos.

Constantes et validations sans I/O. Aucune dépendance FastAPI ni DB.
Comportement identique à api/routers/uploads.py.
"""

from __future__ import annotations

from app.modules.uploads.domain.enums import EntityType

# Types MIME autorisés pour les logos (legacy: ALLOWED_LOGO_MIMETYPES)
ALLOWED_LOGO_MIMETYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/svg+xml",
        "image/webp",
    }
)

# Taille maximale des logos : 2 MB (legacy: MAX_LOGO_SIZE)
MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024

# Facteur de zoom logo : bornes (legacy: scale entre 0.5 et 2.0)
LOGO_SCALE_MIN = 0.5
LOGO_SCALE_MAX = 2.0


def is_allowed_logo_content_type(content_type: str | None) -> bool:
    """Vérifie si le type MIME est autorisé pour un logo."""
    return content_type in ALLOWED_LOGO_MIMETYPES if content_type else False


def is_logo_size_valid(size_bytes: int) -> bool:
    """Vérifie si la taille du fichier est dans la limite."""
    return 0 <= size_bytes <= MAX_LOGO_SIZE_BYTES


def is_logo_scale_valid(scale: float) -> bool:
    """Vérifie si le facteur de zoom est dans la plage autorisée."""
    return LOGO_SCALE_MIN <= scale <= LOGO_SCALE_MAX


def is_valid_entity_type(value: str) -> bool:
    """Vérifie si la valeur est un entity_type autorisé (company ou group)."""
    return value in (e.value for e in EntityType)
