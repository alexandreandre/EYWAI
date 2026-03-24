"""
Règles métier pures pour les sorties de salariés.

À migrer depuis api/routers/employee_exits.py : get_initial_status, get_valid_status_transitions,
règle période de rétractation 15j (rupture conventionnelle).
Aucune dépendance DB ni FastAPI.
"""
from typing import List

# Map exit_type -> statut initial
_INITIAL_STATUS: dict[str, str] = {
    "demission": "demission_recue",
    "rupture_conventionnelle": "rupture_en_negociation",
    "licenciement": "licenciement_convocation",
    "depart_retraite": "demission_effective",
    "fin_periode_essai": "demission_effective",
}

# Map (exit_type, current_status) -> liste des statuts cibles autorisés
_TRANSITIONS: dict[str, dict[str, List[str]]] = {
    "demission": {
        "demission_recue": ["demission_preavis_en_cours", "demission_effective", "annulee"],
        "demission_preavis_en_cours": ["demission_effective", "annulee"],
        "demission_effective": ["archivee"],
    },
    "rupture_conventionnelle": {
        "rupture_en_negociation": ["rupture_validee", "annulee"],
        "rupture_validee": ["rupture_homologuee", "annulee"],
        "rupture_homologuee": ["rupture_effective"],
        "rupture_effective": ["archivee"],
    },
    "licenciement": {
        "licenciement_convocation": ["licenciement_notifie", "annulee"],
        "licenciement_notifie": ["licenciement_preavis_en_cours", "licenciement_effective", "annulee"],
        "licenciement_preavis_en_cours": ["licenciement_effective", "annulee"],
        "licenciement_effective": ["archivee"],
    },
    "depart_retraite": {
        "demission_effective": ["archivee"],
        "archivee": [],
    },
    "fin_periode_essai": {
        "demission_effective": ["archivee"],
        "archivee": [],
    },
}


def get_initial_status(exit_type: str) -> str:
    """Détermine le statut initial selon le type de sortie. Source : router legacy."""
    return _INITIAL_STATUS.get(exit_type, "demission_recue")


def get_valid_status_transitions(exit_type: str, current_status: str) -> List[str]:
    """Retourne les transitions de statut valides. Source : router legacy."""
    return _TRANSITIONS.get(exit_type, {}).get(current_status, [])
