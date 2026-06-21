"""
Module absences — api / application / domain / infrastructure / schemas.

- Router branché dans app/api/router.py via app.modules.absences.api.router.
- Legacy : api/routers/absences.py reste dans main.py tant que nécessaire (ne pas supprimer sans vérifier les usages).
- Compatibilité : schemas/absence.py réexporte ce module (utilisé par legacy + expenses + schemas/expense.py).
"""
