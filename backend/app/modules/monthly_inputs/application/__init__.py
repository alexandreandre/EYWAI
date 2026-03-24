# Application layer for monthly_inputs.
from app.modules.monthly_inputs.application import commands, queries
from app.modules.monthly_inputs.application.commands import (
    create_employee_monthly_input,
    create_monthly_inputs_batch,
    delete_employee_monthly_input,
    delete_monthly_input,
)
from app.modules.monthly_inputs.application.queries import (
    get_primes_catalogue,
    list_monthly_inputs_by_employee_period,
    list_monthly_inputs_by_period,
)

__all__ = [
    "commands",
    "queries",
    "create_monthly_inputs_batch",
    "create_employee_monthly_input",
    "delete_monthly_input",
    "delete_employee_monthly_input",
    "list_monthly_inputs_by_period",
    "list_monthly_inputs_by_employee_period",
    "get_primes_catalogue",
]
