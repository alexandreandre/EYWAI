# Infrastructure layer for monthly_inputs.
from app.modules.monthly_inputs.infrastructure.queries import (
    primes_catalogue_provider,
    SupabasePrimesCatalogueProvider,
)
from app.modules.monthly_inputs.infrastructure.repository import (
    monthly_inputs_repository,
    SupabaseMonthlyInputsRepository,
)

__all__ = [
    "monthly_inputs_repository",
    "SupabaseMonthlyInputsRepository",
    "primes_catalogue_provider",
    "SupabasePrimesCatalogueProvider",
]
