# Module payslips — bulletins de paie.
# Structure cible préparée pour la migration ; router à brancher dans app.api.router.
from app.modules.payslips.api.router import router as payslips_router

__all__ = ["payslips_router"]
