# Application layer for rates.
from app.modules.rates.application.queries import get_all_rates
from app.modules.rates.domain.interfaces import IAllRatesReader

__all__ = ["get_all_rates", "IAllRatesReader"]
