# Application layer for access_control: service, DTOs, queries, commands.
from app.modules.access_control.application.commands import (
    quick_create_role_template,
    require_rh_access,
    require_rh_access_for_company,
)
from app.modules.access_control.application.queries import (
    check_hierarchy,
    check_permission,
    get_all_permissions,
    get_permission_actions,
    get_permission_categories,
    get_permissions_matrix,
    get_role_template_by_id,
    get_role_templates,
    get_user_permissions_summary,
)
from app.modules.access_control.application.service import (
    AccessControlService,
    access_control_service,
    get_access_control_service,
)

__all__ = [
    "AccessControlService",
    "access_control_service",
    "get_access_control_service",
    "check_hierarchy",
    "check_permission",
    "get_permission_categories",
    "get_permission_actions",
    "get_all_permissions",
    "get_permissions_matrix",
    "get_user_permissions_summary",
    "get_role_templates",
    "get_role_template_by_id",
    "require_rh_access",
    "require_rh_access_for_company",
    "quick_create_role_template",
]
