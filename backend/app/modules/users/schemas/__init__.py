"""
Schémas du module users (requêtes et réponses API).

Définitions canoniques dans requests.py et responses.py.
Point d'entrée : from app.modules.users.schemas import User, CompanyAccess, ...
"""
from app.modules.users.schemas.requests import (
    SetPrimaryCompanyRequest,
    UserCompanyAccessCreate,
    UserCompanyAccessCreateByUserId,
    UserCompanyAccessUpdate,
    UserCreateWithPermissions,
    UserUpdateWithPermissions,
    UserCompanyAccessData,
)
from app.modules.users.schemas.responses import (
    User,
    CompanyAccess,
    UserDetail,
    UserSimple,
)

__all__ = [
    "SetPrimaryCompanyRequest",
    "UserCompanyAccessCreate",
    "UserCompanyAccessCreateByUserId",
    "UserCompanyAccessUpdate",
    "UserCreateWithPermissions",
    "UserUpdateWithPermissions",
    "UserCompanyAccessData",
    "User",
    "CompanyAccess",
    "UserDetail",
    "UserSimple",
]
