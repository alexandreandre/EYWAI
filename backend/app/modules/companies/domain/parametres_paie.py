"""
Réglages de paie de la société saisis à l'écran « Paramètres de paie ».

Trois vivent dans `companies.settings` (lus par le moteur via
payslip_generator), l'effectif est une colonne. Chaque validation renvoie la
valeur à écrire ou lève ValueError avec une phrase qui dit quoi corriger.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from datetime import date
from typing import Any

#: Bornes du bonus-malus assurance chômage depuis le 1er mai 2025 (taux de
#: référence 4 %) : plancher 2,95 %, plafond 5 %. Inchangées pour la
#: modulation du 1er septembre 2025 au 28 février 2026 comme pour celle du
#: 1er mars 2026 au 28 février 2027 (travail-emploi.gouv.fr, urssaf.fr).
TAUX_CHOMAGE_MIN = 2.95
TAUX_CHOMAGE_MAX = 5.0

#: Valeurs de `settings.date_paiement` connues du moteur
#: (payroll/engine/bulletin.py, _calculer_date_paiement).
DATES_PAIEMENT: tuple[str, ...] = ("dernier_jour_du_mois", "arrete_des_variables")

#: Réglages rangés dans `companies.settings` ; `None` retire la clé.
CLES_SETTINGS: tuple[str, ...] = ("taux_assurance_chomage", "date_paiement", "jour_solidarite")

_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def valider_taux_assurance_chomage(valeur: Any) -> float | None:
    """Taux notifié en % ; None = retour au taux de droit commun du barème."""
    if valeur is None:
        return None
    if isinstance(valeur, bool):
        raise ValueError("Le taux d'assurance chômage doit être un nombre, par exemple 4,05.")
    if isinstance(valeur, str):
        valeur = valeur.strip().replace(",", ".")
    try:
        taux = float(valeur)
    except (TypeError, ValueError):
        raise ValueError(
            "Le taux d'assurance chômage doit être un nombre, par exemple 4,05."
        ) from None
    if math.isnan(taux) or not TAUX_CHOMAGE_MIN <= taux <= TAUX_CHOMAGE_MAX:
        raise ValueError(
            "Le taux d'assurance chômage notifié est compris entre 2,95 % et 5 % "
            "(bornes du bonus-malus). Laissez le champ vide pour le taux normal."
        )
    return taux


def valider_effectif(valeur: Any) -> int:
    """Effectif retenu pour les seuils : entier, 0 ou plus, jamais vide."""
    message = "L'effectif est un nombre entier, 0 ou plus."
    if valeur is None or isinstance(valeur, bool):
        raise ValueError(message)
    if isinstance(valeur, float):
        if not valeur.is_integer():
            raise ValueError(message)
        valeur = int(valeur)
    if isinstance(valeur, str):
        texte = valeur.strip()
        if not texte.isdigit():
            raise ValueError(message)
        valeur = int(texte)
    if not isinstance(valeur, int) or valeur < 0:
        raise ValueError(message)
    return valeur


def valider_date_paiement(valeur: Any) -> str | None:
    """None = comportement historique (date de l'arrêté des variables)."""
    if valeur is None:
        return None
    if valeur not in DATES_PAIEMENT:
        raise ValueError(
            "La date de paiement est « Dernier jour du mois » ou « Jour de l'arrêté des variables »."
        )
    return str(valeur)


def valider_jour_solidarite(valeur: Any) -> str | None:
    """Date AAAA-MM-JJ ; None = aucune date réglée (le moteur prend le lundi de Pentecôte)."""
    if valeur is None:
        return None
    message = "La journée de solidarité doit être une date valide, par exemple 2026-05-25."
    if isinstance(valeur, date):
        return valeur.isoformat()
    if not isinstance(valeur, str) or not _DATE_ISO.match(valeur.strip()):
        raise ValueError(message)
    try:
        return date.fromisoformat(valeur.strip()).isoformat()
    except ValueError:
        raise ValueError(message) from None


def separer_reglages(update: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(colonnes de companies, réglages de settings) d'un corps de mise à jour."""
    colonnes = {k: v for k, v in update.items() if k not in CLES_SETTINGS}
    reglages = {k: update[k] for k in CLES_SETTINGS if k in update}
    return colonnes, reglages


def fusionner_reglages(
    settings: Mapping[str, Any] | None, reglages: Mapping[str, Any]
) -> dict[str, Any]:
    """Fusionne sans toucher aux autres clés ; une valeur None retire la clé."""
    fusion = dict(settings) if isinstance(settings, Mapping) else {}
    for cle, valeur in reglages.items():
        if valeur is None:
            fusion.pop(cle, None)
        else:
            fusion[cle] = valeur
    return fusion


def _meme_valeur(a: Any, b: Any) -> bool:
    if a == b:
        return True
    if a is None or b is None or isinstance(a, bool) or isinstance(b, bool):
        return False
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return False


def changements(avant: Mapping[str, Any], apres: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Clés de `apres` dont la valeur diffère de `avant`, avec l'avant et l'après."""
    return {
        cle: {"avant": avant.get(cle), "apres": valeur}
        for cle, valeur in apres.items()
        if not _meme_valeur(avant.get(cle), valeur)
    }


def changements_settings(
    avant: Mapping[str, Any] | None, apres: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """Clés de settings ajoutées, modifiées ou retirées."""
    anciens = avant if isinstance(avant, Mapping) else {}
    return {
        cle: {"avant": anciens.get(cle), "apres": apres.get(cle)}
        for cle in sorted(set(anciens) | set(apres))
        if not _meme_valeur(anciens.get(cle), apres.get(cle))
    }
