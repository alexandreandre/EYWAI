"""Schémas API du module copilot (requêtes et réponses)."""
from app.modules.copilot.schemas.requests import (
    AgentMessage,
    AgentRequest,
    QueryRequest,
)
from app.modules.copilot.schemas.responses import (
    AgentResponse,
    QueryResponse,
)

__all__ = [
    "AgentMessage",
    "AgentRequest",
    "AgentResponse",
    "QueryRequest",
    "QueryResponse",
]
