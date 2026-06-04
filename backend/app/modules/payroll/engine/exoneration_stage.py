"""Règles d'exonération pour les gratifications de stage.

Seuil légal : 15 % du plafond horaire SS × heures travaillées sur la période.
Paramètres pilotés par payroll_config (clé ``stage``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger("modules.payroll.engine.exoneration_stage")


def _config_stage(contexte) -> Dict[str, Any]:
    return contexte.baremes.get("stage", {}) or {}


def plafond_exoneration_stage(
    contexte, heures_remunerees_mois: float
) -> float:
    """Plafond mensuel d'exonération de gratification de stage (€)."""
    cfg = _config_stage(contexte)
    pct = float(cfg.get("pct_plafond_horaire_ss", 0.15))

    pss_mensuel = float((contexte.baremes.get("pss", {}) or {}).get("mensuel", 0.0))
    plafond_horaire_cfg = cfg.get("plafond_horaire_ss")
    if plafond_horaire_cfg is not None:
        plafond_horaire = float(plafond_horaire_cfg)
    elif pss_mensuel > 0:
        heures_mensuelles_legales = (35.0 * 52) / 12
        plafond_horaire = pss_mensuel / heures_mensuelles_legales
    else:
        plafond_horaire = 0.0

    heures_mensuelles_contrat = (contexte.duree_hebdo_contrat * 52) / 12
    if heures_mensuelles_contrat <= 0:
        heures_mensuelles_contrat = heures_mensuelles_legales if pss_mensuel else 151.67

    plafond_horaire_exo = plafond_horaire * pct
    return round(plafond_horaire_exo * heures_remunerees_mois, 2)


def assiette_stage_residuelle(brut: float, plafond: float) -> float:
    return round(max(0.0, float(brut) - float(plafond)), 2)


def contexte_exoneration_stage(
    contexte, heures_remunerees_mois: float
) -> Optional[Dict[str, Any]]:
    if not getattr(contexte, "is_stagiaire", False):
        return None
    cfg = _config_stage(contexte)
    if cfg.get("actif") is False:
        return None
    plafond = plafond_exoneration_stage(contexte, heures_remunerees_mois)
    return {
        "plafond": plafond,
        "pct_plafond_horaire_ss": float(cfg.get("pct_plafond_horaire_ss", 0.15)),
    }
