"""Règles B : relire un bulletin déjà calculé, sans rappeler le moteur.

Chaque règle compare deux nombres déjà dans ``payslip_data`` : ce qui est
imprimé, et ce que ses propres lignes redonnent. Un centime d'écart ne lève
rien. Deux centimes lèvent. Aucun modèle, aucune lecture en base.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.modules.payslips.domain.comparison_engine import (
    PayslipAlert,
    _nombre_fr,
    _pct_change,
)

REGLES_BULLETIN = frozenset({"B01", "B02", "B03", "B04"})

_LIGNES_DE_BRUT = ("calcul_du_brut", "details_conges", "details_absences")


def anomalies_du_bulletin(payslip_data: dict | None) -> list[PayslipAlert]:
    """Les écarts de cohérence interne d'un bulletin. Liste vide s'il est juste."""
    if not isinstance(payslip_data, dict):
        return []
    alertes: list[PayslipAlert] = []
    alertes.extend(_cotisations_contre_leur_taux(payslip_data))
    alerte_brut = _brut_contre_ses_lignes(payslip_data)
    if alerte_brut is not None:
        alertes.append(alerte_brut)
    alertes.extend(_totaux_contre_leurs_lignes(payslip_data))
    return alertes


def _lignes_cotisation(payslip_data: dict) -> Iterator[dict]:
    for rubrique in payslip_data.get("cotisations_officielles") or []:
        if not isinstance(rubrique, dict):
            continue
        for ligne in rubrique.get("lignes") or []:
            if isinstance(ligne, dict):
                yield ligne


def _lignes_brut(payslip_data: dict) -> Iterator[dict]:
    """Les lignes qui composent le brut : congés et absences sont à part.

    ``creer_bulletin_final`` les répartit dans trois listes. Le maintien en est
    un extrait, pas une quatrième somme.
    """
    for cle in _LIGNES_DE_BRUT:
        for ligne in payslip_data.get(cle) or []:
            if isinstance(ligne, dict) and not ligne.get("is_sous_total"):
                yield ligne


def _cotisations_contre_leur_taux(payslip_data: dict) -> list[PayslipAlert]:
    alertes: list[PayslipAlert] = []
    for ligne in _lignes_cotisation(payslip_data):
        libelle = str(ligne.get("libelle") or "Cotisation")
        base = _nombre(ligne.get("base"))
        for cote, taux_cle, montant_cle in (
            ("salariale", "taux_salarial", "montant_salarial"),
            ("patronale", "taux_patronal", "montant_patronal"),
        ):
            if ligne.get(taux_cle) is None:
                continue
            rejoue = round(base * _nombre(ligne.get(taux_cle)), 2)
            imprime = _nombre(ligne.get(montant_cle))
            ecart = round(imprime - rejoue, 2)
            if abs(ecart) <= 0.01:
                continue
            alertes.append(
                _alerte(
                    "B01",
                    f"{libelle}:{montant_cle}",
                    imprime,
                    rejoue,
                    (
                        f"La ligne « {libelle} » imprime {_euros(imprime)} de part {cote}. "
                        f"Base × taux donne {_euros(rejoue)} : {_sens(ecart)}."
                    ),
                )
            )
    return alertes


def _brut_contre_ses_lignes(payslip_data: dict) -> PayslipAlert | None:
    if "salaire_brut" not in payslip_data:
        return None
    imprime = _nombre(payslip_data.get("salaire_brut"))
    gains = sum(_nombre(ligne.get("gain")) for ligne in _lignes_brut(payslip_data))
    pertes = sum(_nombre(ligne.get("perte")) for ligne in _lignes_brut(payslip_data))
    rejoue = round(gains - pertes, 2)
    ecart = round(imprime - rejoue, 2)
    if abs(ecart) <= 0.01:
        return None
    return _alerte(
        "B02",
        "salaire_brut",
        imprime,
        rejoue,
        (
            f"Le salaire brut imprimé est {_euros(imprime)}. "
            f"La somme des lignes de brut est {_euros(rejoue)} : {_sens(ecart)}."
        ),
    )


def _totaux_contre_leurs_lignes(payslip_data: dict) -> list[PayslipAlert]:
    structure = payslip_data.get("structure_cotisations")
    if not isinstance(structure, dict):
        return []
    alertes: list[PayslipAlert] = []
    for rule_id, cle, titre in (
        ("B03", "total_salarial", "total salarial"),
        ("B04", "total_patronal", "total patronal"),
    ):
        if cle not in structure:
            continue
        montant_cle = "montant_salarial" if cle == "total_salarial" else "montant_patronal"
        imprime = _nombre(structure.get(cle))
        rejoue = round(
            sum(_nombre(ligne.get(montant_cle)) for ligne in _lignes_cotisation(payslip_data)),
            2,
        )
        ecart = round(imprime - rejoue, 2)
        if abs(ecart) <= 0.01:
            continue
        alertes.append(
            _alerte(
                rule_id,
                cle,
                imprime,
                rejoue,
                (
                    f"Le {titre} imprimé est {_euros(imprime)}. "
                    f"La somme des lignes est {_euros(rejoue)} : {_sens(ecart)}."
                ),
            )
        )
    return alertes


def _alerte(rule_id: str, field: str, imprime: float, rejoue: float, message: str) -> PayslipAlert:
    return PayslipAlert(
        rule_id=rule_id,
        level="CRITIQUE",
        message=message,
        field=field,
        value_n=imprime,
        value_n1=rejoue,
        delta_pct=_pct_change(rejoue, imprime),
        delta_eur=round(imprime - rejoue, 2),
    )


def _sens(ecart: float) -> str:
    montant = _euros(abs(ecart))
    if ecart > 0:
        return f"{montant} de trop"
    return f"{montant} en moins"


def _euros(valeur: float) -> str:
    return f"{_nombre_fr(valeur)} €"


def _nombre(valeur: Any) -> float:
    if isinstance(valeur, bool) or valeur is None:
        return 0.0
    if isinstance(valeur, (int, float)):
        return float(valeur)
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return 0.0
