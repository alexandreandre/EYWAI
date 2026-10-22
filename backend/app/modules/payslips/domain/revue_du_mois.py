"""Revue d'un mois : les règles B et les alertes du moteur, par salarié.

Même ordre que le PDF du mois (nom, puis prénom). Les critiques d'abord.
Une alerte acquittée ou ignorée sort de la liste. Aucun appel, aucune base.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.payroll.engine.controles_convention import (
    extraire_alertes_rh_depuis_bulletin,
)
from app.modules.payslips.domain.anomalies_bulletin import anomalies_du_bulletin
from app.modules.payslips.domain.comparison_engine import (
    PayslipAlert,
    _apply_alerts_status_from_bulletin,
)
from app.modules.payslips.domain.pdf_du_mois import _cle

_NIVEAU = {"CRITIQUE": 0, "AVERTISSEMENT": 1, "INFO": 2}


@dataclass(frozen=True)
class RevueDunSalarie:
    identifiant: str
    prenom: str
    nom: str
    alertes: tuple[PayslipAlert, ...]


def revue_du_mois(personnes: list[dict]) -> list[RevueDunSalarie]:
    """`personnes` : identifiant, prenom, nom, payslip_data. Sans alerte, le salarié n'y est pas."""
    revues: list[RevueDunSalarie] = []
    for personne in personnes:
        if not isinstance(personne, dict):
            continue
        donnees = personne.get("payslip_data")
        if not isinstance(donnees, dict):
            continue
        alertes = _alertes(donnees)
        if not alertes:
            continue
        revues.append(
            RevueDunSalarie(
                identifiant=str(personne.get("identifiant") or ""),
                prenom=str(personne.get("prenom") or ""),
                nom=str(personne.get("nom") or ""),
                alertes=tuple(alertes),
            )
        )
    revues.sort(key=lambda revue: _cle(revue.prenom, revue.nom))
    return revues


def _alertes(donnees: dict) -> list[PayslipAlert]:
    alertes = anomalies_du_bulletin(donnees)
    for brute in extraire_alertes_rh_depuis_bulletin(donnees):
        alertes.append(
            PayslipAlert(
                rule_id=str(brute.get("code") or "alerte_paie"),
                level="CRITIQUE" if brute.get("severite") == "bloquant" else "AVERTISSEMENT",
                message=str(brute.get("message") or ""),
                field=str(brute.get("source") or "moteur"),
                value_n=0.0,
                value_n1=0.0,
                delta_pct=0.0,
            )
        )
    _apply_alerts_status_from_bulletin(alertes, donnees.get("alerts_status"))
    actives = [alerte for alerte in alertes if alerte.status == "active" and alerte.message]
    actives.sort(key=lambda alerte: _NIVEAU.get(alerte.level, 9))
    return actives
