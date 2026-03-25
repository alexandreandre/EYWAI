"""
Module absences — api / application / domain / infrastructure / schemas.

- Router branché dans app/api/router.py (nouveau).
- Legacy : api/routers/absences.py reste dans main.py tant que nécessaire (ne pas supprimer sans vérifier les usages).
- Compatibilité : schemas/absence.py réexporte ce module (utilisé par legacy + expenses + schemas/expense.py).
"""

from app.modules.absences.api.router import router

__all__ = ["router"]
