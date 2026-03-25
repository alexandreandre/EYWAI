# app/modules/recruitment/__init__.py
"""
Module Recrutement (ATS) : jobs, pipeline, candidats, entretiens, notes, avis, timeline.
Structure cible préparée pour migration depuis api/routers/recruitment.py et services/recruitment_service.py.
"""

from app.modules.recruitment.api.router import router

__all__ = ["router"]
