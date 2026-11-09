"""Ce que le bulletin de sortie rappelle à la gestionnaire (R-303, R-316, R-317).

Des avertissements : aucun montant ne bouge, la validation reste possible.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.modules.payroll.engine.bulletin import _jours_fr
from app.modules.payroll.engine.calcul_brut import _est_une_iccp

logger = get_logger(__name__)


def _alerte(code: str, message: str, **extra: Any) -> Dict[str, Any]:
    return {"code": code, "severity": "warning", "critique": False, "message": message, **extra}


def _solde_cp(solde_conges: Optional[Dict[str, Any]]) -> float:
    total = 0.0
    for cle in ("conges_payes", "conges_payes_periode_precedente"):
        compteur = (solde_conges or {}).get(cle)
        if isinstance(compteur, dict):
            total += max(0.0, float(compteur.get("solde") or 0.0))
    return round(total, 2)


def alerte_sortie_sans_iccp(
    solde_conges: Optional[Dict[str, Any]],
    details_brut: List[Dict[str, Any]],
    *,
    iccp_du_dossier: bool,
) -> List[Dict[str, Any]]:
    """Solde de congés positif, et aucune indemnité compensatrice sur le bulletin
    ni dans le dossier de départ : elle est due quelle que soit la cause de la
    rupture (C. trav. L3141-28, ouvert le 08/11/2026)."""
    solde = _solde_cp(solde_conges)
    if solde <= 0 or iccp_du_dossier or any(
        _est_une_iccp(l.get("libelle")) and float(l.get("gain") or 0) > 0 for l in details_brut
    ):
        return []
    return [
        _alerte(
            "sortie_sans_indemnite_conges",
            f"Départ : {_jours_fr(solde)} de congés payés restants et aucune indemnité "
            "compensatrice sur ce bulletin. Elle est due quelle que soit la cause de "
            "la rupture (C. trav. L3141-28) : vérifiez le dossier de départ, ou "
            "ajoutez-la depuis la page Primes.",
        )
    ]


def _solde_cet_en_heures(employee_id: str, company_id: str) -> float:
    from app.modules.cet.application.queries import _movement_rows
    from app.modules.cet.domain.rules import compute_cet_balance_hours
    from app.modules.cet.infrastructure import repository as cet_repo

    reglages = cet_repo.get_cet_settings_row(company_id)
    return compute_cet_balance_hours(
        _movement_rows(cet_repo.list_movements_for_employee(employee_id)),
        hours_per_rest_day=float(reglages.get("hours_per_rest_day") or 7),
    )


def alerte_cet_au_depart(employee_id: str, company_id: str) -> List[Dict[str, Any]]:
    """Solde au CET : à défaut de transfert, le salarié perçoit la conversion
    monétaire de ses droits (C. trav. L3153-2, 1°, ouvert le 08/11/2026)."""
    solde = _solde_cet_en_heures(employee_id, company_id)
    if solde <= 0:
        return []
    from app.modules.modulation.domain.hour_account_rules import heures_en_texte

    return [
        _alerte(
            "cet_a_payer_au_depart",
            f"Départ : {heures_en_texte(solde)} au compte épargne-temps. À défaut "
            "de transfert prévu par accord, le salarié perçoit la conversion monétaire "
            "de ses droits (C. trav. L3153-2) : Martine ne la paie pas seule, "
            "ajoutez-la depuis la page Primes.",
        )
    ]


def _reglages_modulation(company_id: str) -> Optional[Dict[str, Any]]:
    from app.modules.modulation.infrastructure import repository as repo

    return repo.get_modulation_settings_row(company_id)


def _mouvements_du_compteur(employee_id: str) -> List[Dict[str, Any]]:
    from app.modules.modulation.infrastructure import repository as repo

    return repo.list_movements_for_employee(employee_id)


def alerte_modulation_au_depart(employee_id: str, company_id: str) -> List[Dict[str, Any]]:
    """Compteur d'heures ouvert mais vide, société qui paie ses heures : un solde
    de modulation suivi hors de Martine (Cartol, payé en heures sup à la sortie
    par Quadra) n'apparaît nulle part sur le bulletin. À vérifier."""
    reglages = _reglages_modulation(company_id)
    if not reglages or not reglages.get("hour_account_enabled"):
        return []
    if reglages.get("hs_routing_policy") != "pay_all" or _mouvements_du_compteur(employee_id):
        return []
    return [
        _alerte(
            "solde_modulation_a_verifier_au_depart",
            "Départ : aucun compteur d'heures tenu dans Martine pour ce salarié. Si "
            "la société suit un solde de modulation ailleurs, il se paie à la sortie : "
            "ajoutez-le depuis la page Primes.",
        )
    ]


def alertes_de_sortie(
    employee_id: Optional[str],
    company_id: Optional[str],
    solde_conges: Optional[Dict[str, Any]],
    details_brut: List[Dict[str, Any]],
    *,
    iccp_du_dossier: bool,
) -> List[Dict[str, Any]]:
    """Les rappels du bulletin de sortie ; une lecture ratée se dit, sans bloquer."""
    alertes = alerte_sortie_sans_iccp(solde_conges, details_brut, iccp_du_dossier=iccp_du_dossier)
    if not employee_id:
        return alertes
    try:
        if not company_id:
            from app.modules.absences.infrastructure.queries import get_employee_company_id

            company_id = get_employee_company_id(employee_id)
        if company_id:
            alertes.extend(alerte_cet_au_depart(employee_id, company_id))
            alertes.extend(alerte_modulation_au_depart(employee_id, company_id))
    except Exception:  # noqa: BLE001 — un rappel raté ne doit pas priver du bulletin, mais se dit
        logger.warning("Compteurs de départ illisibles", exc_info=True)
        alertes.append(
            _alerte(
                "compteurs_de_depart_illisibles",
                "Départ : le compte épargne-temps et le compteur d'heures n'ont pas "
                "pu être relus. Vérifiez qu'aucun solde n'est à payer sur ce bulletin.",
            )
        )
    return alertes
