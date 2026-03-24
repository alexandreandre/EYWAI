# Application layer for collective_agreements (placeholders pour migration).
from . import commands  # noqa: F401
from . import queries  # noqa: F401
from .service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)

__all__ = [
    "commands",
    "queries",
    "CollectiveAgreementsService",
    "get_collective_agreements_service",
]
