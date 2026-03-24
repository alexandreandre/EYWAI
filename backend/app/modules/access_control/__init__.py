"""
Module access_control : centralisation des permissions et helpers d'autorisation métier.

- api/router.py : tous les endpoints (catégories, actions, permissions, matrice, templates, check-hierarchy, check-permission), préfixe /api/access-control, branché dans app/api/router.py.
- application/ : queries, commands, service (require_rh_access, require_rh_access_for_company, quick_create_role_template, etc.).
- schemas/responses.py : PermissionCheckResponse, RoleHierarchyCheckResponse (définitions canoniques ; réexport dans schemas.permissions pour legacy).

Routers legacy (api/routers/user_management, users, employee_exits) conservent leurs imports et comportement ; ils utilisent encore les fonctions locales ou schemas.permissions. Ne pas supprimer ces imports tant que les clients n'ont pas basculé vers /api/access-control.
"""
from app.modules.access_control.application import (
    AccessControlService,
    access_control_service,
    get_access_control_service,
)

__all__ = [
    "AccessControlService",
    "access_control_service",
    "get_access_control_service",
]
