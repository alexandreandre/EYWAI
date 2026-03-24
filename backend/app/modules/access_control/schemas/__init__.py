# Schemas for access_control. Définitions canoniques du module (pas d'import legacy).
from app.modules.access_control.schemas.catalog import (
    Permission,
    PermissionAction,
    PermissionCategory,
    PermissionMatrix,
    PermissionMatrixCategory,
    PermissionWithMetadata,
    RoleTemplateDetail,
    RoleTemplateQuickCreate,
    RoleTemplateWithPermissions,
    UserPermissionsSummary,
)
from app.modules.access_control.schemas.responses import (
    PermissionCheckResponse,
    RoleHierarchyCheckResponse,
)

__all__ = [
    "PermissionCheckResponse",
    "RoleHierarchyCheckResponse",
    "PermissionCategory",
    "PermissionAction",
    "Permission",
    "PermissionMatrix",
    "PermissionMatrixCategory",
    "PermissionWithMetadata",
    "UserPermissionsSummary",
    "RoleTemplateDetail",
    "RoleTemplateQuickCreate",
    "RoleTemplateWithPermissions",
]
