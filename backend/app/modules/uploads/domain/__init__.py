# Domain layer for uploads.
from app.modules.uploads.domain.enums import EntityType
from app.modules.uploads.domain.rules import (
    ALLOWED_LOGO_MIMETYPES,
    LOGO_SCALE_MAX,
    LOGO_SCALE_MIN,
    MAX_LOGO_SIZE_BYTES,
    is_allowed_logo_content_type,
    is_logo_scale_valid,
    is_logo_size_valid,
    is_valid_entity_type,
)

__all__ = [
    "EntityType",
    "ALLOWED_LOGO_MIMETYPES",
    "LOGO_SCALE_MAX",
    "LOGO_SCALE_MIN",
    "MAX_LOGO_SIZE_BYTES",
    "is_allowed_logo_content_type",
    "is_logo_scale_valid",
    "is_logo_size_valid",
    "is_valid_entity_type",
]
