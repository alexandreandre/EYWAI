# Domain layer for collective_agreements (règles pures, interfaces, pas de FastAPI).
from app.modules.collective_agreements.domain import exceptions, rules

__all__ = ["exceptions", "rules"]
