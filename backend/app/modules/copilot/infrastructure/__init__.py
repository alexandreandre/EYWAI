"""
Couche infrastructure du module copilot.

- schema_context : constantes de schéma BDD pour le LLM
- sql_executor : exécution SQL en lecture (Supabase RPC)
- queries : requêtes Supabase (profiles, employees, conventions)
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
from app.modules.copilot.infrastructure.sql_executor import (
    SupabaseSqlExecutor,
    get_sql_executor,
)

__all__ = [
    "CollectiveAgreementProvider",
    "EmployeeSearchProvider",
    "OpenAIProvider",
    "SupabaseSqlExecutor",
    "UserCompanyResolver",
    "get_collective_agreement_provider",
    "get_employee_search_provider",
    "get_openai_provider",
    "get_sql_executor",
    "get_user_company_resolver",
]
