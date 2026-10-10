"""Règles d'exonération pour les gratifications de stage.

Franchise : 15 % du plafond horaire de la Sécurité sociale × heures de stage
du mois. Urssaf, « Accueillir un stagiaire étudiant » (2026 : plafond horaire
30 €, gratification minimale et limite d'exonération 4,50 € par heure) :
https://www.urssaf.fr/accueil/employeur/embaucher-gerer-salaries/embaucher/stagiaire-etudiant.html

Le plafond horaire est fixé par arrêté : il vient des barèmes
(`payroll_config.stage.plafond_horaire_ss`, sinon `payroll_config.pss.horaire`), jamais du plafond mensuel divisé
par 151,67 h (4 005 / 151,67 × 15 % = 3,96 €/h au lieu de 4,50 €). Sans valeur
dans les barèmes, aucune franchise n'est devinée : la gratification est cotisée
en entier et une alerte le dit sur le bulletin.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger("modules.payroll.engine.exoneration_stage")

CODE_ALERTE_PLAFOND_HORAIRE_ABSENT = "stage_plafond_horaire_ss_absent"


def _config_stage(contexte) -> Dict[str, Any]:
    return contexte.baremes.get("stage", {}) or {}


def plafond_horaire_ss(contexte) -> Optional[float]:
    """Plafond horaire de la Sécurité sociale du barème (`stage`, sinon `pss.horaire`,
    valeur officielle de l'arrêté), ou None s'il manque."""
    pss = contexte.baremes.get("pss", {}) or {}
    for valeur in (_config_stage(contexte).get("plafond_horaire_ss"), pss.get("horaire")):
        try:
            plafond = float(valeur) if valeur is not None else None
        except (TypeError, ValueError):
            continue
        if plafond and plafond > 0:
            return plafond
    return None


def plafond_exoneration_stage(
    contexte, heures_remunerees_mois: float
) -> Optional[float]:
    """Plafond mensuel d'exonération de gratification de stage (€), ou None
    quand le plafond horaire officiel manque aux barèmes."""
    plafond_horaire = plafond_horaire_ss(contexte)
    if plafond_horaire is None:
        return None
    pct = float(_config_stage(contexte).get("pct_plafond_horaire_ss", 0.15))
    return round(plafond_horaire * pct * heures_remunerees_mois, 2)


def assiette_stage_residuelle(brut: float, plafond: float) -> float:
    return round(max(0.0, float(brut) - float(plafond)), 2)


def _alerter_plafond_horaire_absent(contexte) -> None:
    alertes = getattr(contexte, "alertes_baremes", None)
    if not isinstance(alertes, list):
        return
    if any(a.get("code") == CODE_ALERTE_PLAFOND_HORAIRE_ABSENT for a in alertes):
        return
    alertes.append(
        {
            "code": CODE_ALERTE_PLAFOND_HORAIRE_ABSENT,
            "config_key": "stage",
            "chemin": ["plafond_horaire_ss"],
            "critique": True,
            "severity": "warning",
            "message": (
                "Gratification de stage cotisée en entier : le plafond horaire de la "
                "Sécurité sociale manque aux barèmes, la franchise (15 % de ce plafond "
                "par heure de stage) n'est pas appliquée. À vérifier avant de valider "
                "ce bulletin : contactez le support."
            ),
            "donnee_non_officielle": True,
        }
    )
    logger.warning("Barème stage sans plafond_horaire_ss : franchise non appliquée")


def contexte_exoneration_stage(
    contexte, heures_remunerees_mois: float
) -> Optional[Dict[str, Any]]:
    if not getattr(contexte, "is_stagiaire", False):
        return None
    cfg = _config_stage(contexte)
    if cfg.get("actif") is False:
        return None
    plafond = plafond_exoneration_stage(contexte, heures_remunerees_mois)
    if plafond is None:
        _alerter_plafond_horaire_absent(contexte)
        return None
    return {
        "plafond": plafond,
        "pct_plafond_horaire_ss": float(cfg.get("pct_plafond_horaire_ss", 0.15)),
    }
