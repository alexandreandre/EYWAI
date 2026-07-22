"""
Couche infrastructure du module copilot.

- queries : requêtes Supabase (profiles, employees, conventions)
- secure_queries : catalogue de requêtes RH strictement scopées
- providers : OpenAIProvider, EmployeeSearchProvider, CollectiveAgreementProvider, UserCompanyResolver
"""

from app.modules.copilot.infrastructure.providers import (
    CollectiveAgreementProvider,
    EmployeeSearchProvider,
    OpenAIProvider,
    UserCompanyResolver,
    get_collective_agreement_provider,
    get_employee_search_provider,
    get_openai_provider,
    get_user_company_resolver,
)
__all__ = [
    "CollectiveAgreementProvider",
    "EmployeeSearchProvider",
    "OpenAIProvider",
    "UserCompanyResolver",
    "get_collective_agreement_provider",
    "get_employee_search_provider",
    "get_openai_provider",
    "get_user_company_resolver",
]
