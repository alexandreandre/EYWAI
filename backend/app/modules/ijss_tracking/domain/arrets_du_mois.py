"""Écran « Arrêts et IJ » (retour d'Elsa du 16/11) : règles pures.

Un arrêt par ligne : ses dates, la subrogation, les IJ du mois (estimées par
Martine, reçues et saisies par la RH) et ce que le bulletin a fait du maintien.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any, Literal

#: Les pièces qu'on peut joindre à un arrêt, toutes facultatives.
TypeJustificatif = Literal["virement_cpam", "ij_salarie", "decompte_cpam", "autre"]
TYPES_JUSTIFICATIF: tuple[str, ...] = (
    "virement_cpam",
    "ij_salarie",
    "decompte_cpam",
    "autre",
)

EtatMaintien = Literal[
    "bulletin_a_faire",
    "en_attente_des_ij",
    "verse",
    "sans_maintien",
]


def _jour(valeur: Any) -> date | None:
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur.strip():
        try:
            return date.fromisoformat(valeur[:10])
        except ValueError:
            return None
    return None


def bornes_arret(jours: Iterable[Any]) -> tuple[date | None, date | None]:
    """Premier et dernier jour de l'arrêt."""
    dates = sorted(d for d in (_jour(j) for j in jours or []) if d)
    if not dates:
        return None, None
    return dates[0], dates[-1]


def jours_dans_le_mois(jours: Iterable[Any], annee: int, mois: int) -> int:
    """Jours calendaires de l'arrêt tombant dans le mois."""
    return sum(
        1
        for d in (_jour(j) for j in jours or [])
        if d and d.year == annee and d.month == mois
    )


def etat_du_maintien(payslip_data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Ce que le bulletin du mois a fait du maintien de salaire.

    Sans bulletin : « bulletin à faire ». En attente des IJ : le réglage
    « maintien après réception des IJ » retient le maintien (montant estimé
    rendu). Sinon : versé, ou pas de maintien avec son motif.
    """
    if not payslip_data:
        return {
            "etat": "bulletin_a_faire",
            "montant_verse": 0.0,
            "montant_en_attente": 0.0,
            "motif": None,
        }
    bloc = payslip_data.get("bloc_maintien") or {}
    maintien = bloc.get("maintien") or {}
    if maintien.get("en_attente_des_ij"):
        return {
            "etat": "en_attente_des_ij",
            "montant_verse": 0.0,
            "montant_en_attente": round(
                float(maintien.get("maintien_en_attente") or 0.0), 2
            ),
            "motif": maintien.get("motif_non_maintien"),
        }
    verse = round(float(maintien.get("maintien_verse") or 0.0), 2)
    if verse > 0:
        return {
            "etat": "verse",
            "montant_verse": verse,
            "montant_en_attente": 0.0,
            "motif": None,
        }
    return {
        "etat": "sans_maintien",
        "montant_verse": 0.0,
        "montant_en_attente": 0.0,
        "motif": maintien.get("motif_non_maintien"),
    }


def ij_estimees_du_bulletin(payslip_data: Mapping[str, Any] | None) -> float | None:
    """IJ brutes estimées par Martine sur le bulletin du mois, si elle en a."""
    if not payslip_data:
        return None
    ijss = (payslip_data.get("bloc_maintien") or {}).get("ijss") or {}
    valeur = ijss.get("ijss_theorique")
    if valeur is None:
        valeur = (payslip_data.get("synthese_net") or {}).get("ijss_subrogees")
    try:
        return round(float(valeur), 2) if valeur is not None else None
    except (TypeError, ValueError):
        return None


def refus_montant_ij(montant: Any) -> str | None:
    """Le montant saisi : un nombre positif ou nul, en euros."""
    try:
        valeur = float(montant)
    except (TypeError, ValueError):
        return "Indiquez le montant brut des IJ du mois, en euros."
    if valeur < 0:
        return "Le montant des IJ ne peut pas être négatif."
    if valeur > 100_000:
        return "Ce montant d'IJ paraît faux : vérifiez la saisie."
    return None
