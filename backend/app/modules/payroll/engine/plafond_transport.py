"""Plafond annuel d'exonération de la prise en charge des trajets domicile-travail.

Contrairement aux plafonds repas, unitaires, celui-ci est annuel et cumulatif
par salarié — toute la mécanique d'exonération existante raisonne ligne par
ligne et mois par mois, d'où ce module dédié.

Les valeurs proviennent du barème URSSAF scrapé (section mobilite_durable,
employeurs_prives), présent en base et affiché dans « Suivi des taux », mais
qui n'était lu par aucun code du moteur jusqu'ici.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.payroll.engine.calcul_frais import sections_frais_pro


def plafond_annuel_transport(
    frais_pro: Optional[Dict[str, Any]],
    *,
    avec_abonnement_public: bool = False,
) -> Optional[float]:
    """Plafond annuel applicable (€), None si le barème est absent.

    Le plafond est relevé lorsque le salarié bénéficie aussi de la prise en
    charge obligatoire de 50 % d'un abonnement de transport public.
    """
    sections = sections_frais_pro(frais_pro)
    mobilite = sections.get("mobilite_durable") or {}
    if not isinstance(mobilite, dict):
        return None
    prives = mobilite.get("employeurs_prives") or {}
    if not isinstance(prives, dict):
        return None
    cle = "limite_cumul_transport_public" if avec_abonnement_public else "limite_base"
    valeur = prives.get(cle)
    if isinstance(valeur, (int, float)) and valeur > 0:
        return float(valeur)
    return None


def depassement_annuel(cumul_verse: float, plafond: Optional[float]) -> float:
    """Part du cumul annuel excédant le plafond, 0 si le plafond est inconnu."""
    if plafond is None:
        return 0.0
    return round(max(0.0, float(cumul_verse) - float(plafond)), 2)
