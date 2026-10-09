"""Métadonnées légères extraites de payslip_data pour les listes API."""

from __future__ import annotations

from typing import Any

from app.modules.payroll.domain.empreinte_entrees import (
    empreinte_complementaire_stockee,
    empreinte_cumuls_stockee,
    empreinte_stockee,
)
from app.modules.payroll.engine.controles_convention import (
    avertissements_de_generation,
)


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


def heures_sup_du_bulletin(payslip_data: Any) -> float | None:
    """Heures sup du mois, lues sur les lignes de brut. None si le bulletin n'en a pas."""
    if not isinstance(payslip_data, dict):
        return None
    lignes = payslip_data.get("calcul_du_brut")
    if not isinstance(lignes, list):
        return None
    total = 0.0
    vu = False
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        libelle = str(ligne.get("libelle") or "")
        if "Heures suppl." not in libelle or "major" not in libelle.lower():
            continue
        quantite = _nombre(ligne.get("quantite"))
        if quantite is None:
            continue
        total += quantite
        vu = True
    return round(total, 2) if vu else 0.0


def montants_du_bulletin(payslip_data: Any) -> dict[str, float | None]:
    """Heures sup, brut et net : ce que le toast de recalcul compare."""
    if not isinstance(payslip_data, dict):
        return {"heures_sup": None, "salaire_brut": None, "net_a_payer": None}
    return {
        "heures_sup": heures_sup_du_bulletin(payslip_data),
        "salaire_brut": _nombre(payslip_data.get("salaire_brut")),
        "net_a_payer": _nombre(payslip_data.get("net_a_payer")),
    }


def regles_acquittees(payslip_data: Any) -> list[str]:
    """Règles de comparaison que la RH a acquittées ou ignorées sur ce bulletin."""
    statuts = payslip_data.get("alerts_status") if isinstance(payslip_data, dict) else None
    if not isinstance(statuts, dict):
        return []
    return sorted(
        str(regle)
        for regle, entree in statuts.items()
        if isinstance(entree, dict) and entree.get("status") in ("acquittee", "ignoree")
    )


def payslip_list_meta(payslip_data: Any) -> dict[str, Any]:
    """net_a_payer, alertes RH et points à arbitrer depuis payslip_data.

    Un point à arbitrer (plafond transport…) n'est pas une alerte : la liste le
    montre discrètement, hors du compte des alertes."""
    vide = {
        "net_a_payer": None,
        "salaire_brut": None,
        "heures_sup": None,
        "empreinte_entrees": None,
        "empreinte_cumuls_precedents": None,
        "empreinte_complementaire": None,
        "warnings": [],
        "points_a_arbitrer": [],
        "alertes_acquittees": [],
    }
    if not isinstance(payslip_data, dict):
        return vide

    montants = montants_du_bulletin(payslip_data)

    warnings: list[str] = []
    points_a_arbitrer: list[str] = []
    for avertissement in avertissements_de_generation(payslip_data):
        if isinstance(avertissement, str):
            warnings.append(avertissement)
        elif avertissement.get("severity") == "info":
            points_a_arbitrer.append(str(avertissement.get("message") or ""))
        else:
            warnings.append(str(avertissement.get("message") or ""))

    # Forçage d'un calendrier incomplet : l'alerte reste sur la ligne.
    for forcage in payslip_data.get("avertissements_forces") or []:
        message = str(forcage.get("message") or "") if isinstance(forcage, dict) else ""
        if message and message not in warnings:
            warnings.append(message)

    return {
        "net_a_payer": montants["net_a_payer"],
        "salaire_brut": montants["salaire_brut"],
        "heures_sup": montants["heures_sup"],
        "empreinte_entrees": empreinte_stockee(payslip_data),
        "empreinte_cumuls_precedents": empreinte_cumuls_stockee(payslip_data),
        "empreinte_complementaire": empreinte_complementaire_stockee(payslip_data),
        "warnings": warnings,
        "points_a_arbitrer": points_a_arbitrer,
        "alertes_acquittees": regles_acquittees(payslip_data),
    }
