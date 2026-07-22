# Schemas for access_control. Définitions canoniques du module (pas d'import legacy).
from app.modules.access_control.schemas.catalog import (
    Permission,
    PermissionAction,
    PermissionCategory,
    PermissionGrantDetail,
    PermissionGrantInput,
    PermissionMatrix,
    PermissionMatrixCategory,
    PermissionTargetInput,
    PermissionWithMetadata,
    RoleTemplateDetail,
    RoleTemplateQuickCreate,
    RoleTemplateWithPermissions,
    UserPermissionsSummary,
    UserPermissionsUpdate,
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
    "UserPermissionsUpdate",
    "PermissionGrantInput",
    "PermissionGrantDetail",
    "PermissionTargetInput",
    "RoleTemplateDetail",
    "RoleTemplateQuickCreate",
    "RoleTemplateWithPermissions",
]
