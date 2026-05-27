# AI / LLM integrations (OpenRouter).

from app.shared.infrastructure.ai.client import (
    chat_completions_create,
    get_chat_client,
    get_llm_api_key,
    is_llm_configured,
    require_llm_api_key,
    resolve_model,
)
from app.shared.infrastructure.ai.models import (
    GPT_4O_MINI,
    MODEL_COLLECTIVE_AGREEMENT_CHAT,
    MODEL_COMPETENCIES_MOBILITY,
    MODEL_CONTRACT_EXTRACTION,
    MODEL_COPILOT,
    MODEL_CSE_RECORDING,
    MODEL_RECRUITMENT_SCORING,
    MODEL_SCRAPING_EXTRACTION,
)

__all__ = [
    "GPT_4O_MINI",
    "MODEL_COLLECTIVE_AGREEMENT_CHAT",
    "MODEL_COMPETENCIES_MOBILITY",
    "MODEL_CONTRACT_EXTRACTION",
    "MODEL_COPILOT",
    "MODEL_CSE_RECORDING",
    "MODEL_RECRUITMENT_SCORING",
    "MODEL_SCRAPING_EXTRACTION",
    "chat_completions_create",
    "get_chat_client",
    "get_llm_api_key",
    "is_llm_configured",
    "require_llm_api_key",
    "resolve_model",
]
