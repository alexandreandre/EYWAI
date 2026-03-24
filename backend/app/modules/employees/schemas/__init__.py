# Schémas du module employees : définitions canoniques en requests/responses ;
# ContractResponse depuis app.shared ; PromotionListItem et EmployeeRhAccess définis dans responses.
from app.modules.employees.schemas.requests import NewFullEmployee, UpdateEmployee
from app.modules.employees.schemas.responses import (
    ContractResponse,
    EmployeeRhAccess,
    FullEmployee,
    NewEmployeeResponse,
    PromotionListItem,
)

__all__ = [
    "NewFullEmployee",
    "UpdateEmployee",
    "FullEmployee",
    "NewEmployeeResponse",
    "ContractResponse",
    "EmployeeRhAccess",
    "PromotionListItem",
]
