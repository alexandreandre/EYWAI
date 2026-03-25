# app/modules/recruitment/application/__init__.py
"""
Couche application recruitment : commands (écritures), queries (lectures), service (logique métier).
Les routers délèguent ici ; aucun accès DB direct dans les routers.
"""

from . import commands, queries, service

__all__ = ["commands", "queries", "service"]
