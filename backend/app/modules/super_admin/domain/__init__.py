# Domain layer for super_admin. Règles métier pures, pas de FastAPI.
from app.modules.super_admin.domain.entities import SuperAdmin
from app.modules.super_admin.domain.enums import SystemHealthStatus
from app.modules.super_admin.domain.exceptions import SuperAdminPermissionDenied
from app.modules.super_admin.domain.value_objects import SuperAdminPermissions

__all__ = [
    "SuperAdmin",
    "SuperAdminPermissions",
    "SystemHealthStatus",
    "SuperAdminPermissionDenied",
]
