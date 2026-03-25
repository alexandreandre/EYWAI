# app/modules/cse/__init__.py
"""
Module CSE & Dialogue Social — structure cible préparée pour migration.
Ne déplace pas le code existant ; placeholders et wrappers uniquement.
"""

__all__ = ["router"]


def __getattr__(name: str):
    """Import paresseux du router pour ne pas charger FastAPI lors d'import des schémas."""
    if name == "router":
        from app.modules.cse.api.router import router

        return router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
