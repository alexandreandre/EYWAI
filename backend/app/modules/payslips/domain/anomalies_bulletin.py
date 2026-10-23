"""Règles B : relire un bulletin déjà calculé, sans rappeler le moteur.

Chaque règle compare deux nombres déjà dans ``payslip_data`` : ce qui est
imprimé, et ce que ses propres lignes redonnent. Un centime d'écart ne lève
rien. Deux centimes lèvent. Aucun modèle, aucune lecture en base.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.modules.payslips.domain.comparison_engine import (
    REGLES_CONNUES,
    PayslipAlert,
    _nombre_fr,
    _pct_change,
)

REGLES_BULLETIN = frozenset({"B01", "B02", "B03", "B04"})


def regles_acquittables() -> frozenset[str]:
    """Les règles R et B qu'une personne peut acquitter ou ignorer."""
    return REGLES_CONNUES | REGLES_BULLETIN

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
    alertes.extend(_rubriques_contre_leurs_lignes(payslip_data))
    return alertes


def _lignes_cotisation(payslip_data: dict) -> Iterator[dict]:
    """Les lignes imprimées. Les bulletins récents les rangent par rubrique.

    Un bulletin plus ancien les laisse dans les blocs de ``structure_cotisations``.
    On ne somme pas les deux : ce serait compter chaque ligne deux fois.
    """
    officielles = payslip_data.get("cotisations_officielles")
    if isinstance(officielles, list) and officielles:
        for rubrique in officielles:
            if not isinstance(rubrique, dict):
                continue
            for ligne in rubrique.get("lignes") or []:
                if isinstance(ligne, dict):
                    yield ligne
        return
    structure = payslip_data.get("structure_cotisations")
    if not isinstance(structure, dict):
        return
    for cle, valeur in structure.items():
        if cle.startswith("total_"):
            continue
        lignes = valeur.get("lignes") if isinstance(valeur, dict) else valeur
        if not isinstance(lignes, list):
            continue
        for ligne in lignes:
            if isinstance(ligne, dict) and (
                "montant_salarial" in ligne or "montant_patronal" in ligne
            ):
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


# Le taux stocké n'est pas un taux du mois : coefficient annuel, ou forfait.
_HORS_PRODUIT = frozenset({"reduction_generale", "mutuelle"})


def _taux_proportionnel(ligne: dict) -> bool:
    """Une mutuelle est un forfait. La réduction générale est un coefficient annuel.

    Un ancien bulletin peut quand même porter un taux (1 % affiché, coefficient
    de l'année). ``base × taux`` ne redonne pas le montant. Le rejouer demande
    le contrat ou les cumuls.
    """
    if ligne.get("coti_id") in _HORS_PRODUIT:
        return False
    return str(ligne.get("libelle") or "") != "Réduction générale de cotisations patronales"


def _cotisations_contre_leur_taux(payslip_data: dict) -> list[PayslipAlert]:
    alertes: list[PayslipAlert] = []
    for ligne in _lignes_cotisation(payslip_data):
        if not _taux_proportionnel(ligne):
            continue
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


def _lignes_du_total(payslip_data: dict) -> list[dict]:
    """Les lignes dont la somme a produit le total stocké.

    Ce total est la somme des blocs. Les rubriques officielles sont un autre
    rangement : un ancien bulletin peut les faire diverger sans que le total
    mente sur ses propres lignes.
    """
    structure = payslip_data.get("structure_cotisations")
    if isinstance(structure, dict):
        lignes: list[dict] = []
        for cle, valeur in structure.items():
            if cle.startswith("total_"):
                continue
            brut = valeur.get("lignes") if isinstance(valeur, dict) else valeur
            if not isinstance(brut, list):
                continue
            lignes.extend(
                ligne
                for ligne in brut
                if isinstance(ligne, dict)
                and ("montant_salarial" in ligne or "montant_patronal" in ligne)
            )
        if lignes:
            return lignes
    return list(_lignes_cotisation(payslip_data))


def _totaux_contre_leurs_lignes(payslip_data: dict) -> list[PayslipAlert]:
    structure = payslip_data.get("structure_cotisations")
    if not isinstance(structure, dict):
        return []
    alertes: list[PayslipAlert] = []
    lignes = _lignes_du_total(payslip_data)
    for rule_id, cle, titre in (
        ("B03", "total_salarial", "total salarial"),
        ("B04", "total_patronal", "total patronal"),
    ):
        if cle not in structure:
            continue
        montant_cle = "montant_salarial" if cle == "total_salarial" else "montant_patronal"
        imprime = _nombre(structure.get(cle))
        rejoue = round(sum(_nombre(ligne.get(montant_cle)) for ligne in lignes), 2)
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


def _rubriques_contre_leurs_lignes(payslip_data: dict) -> list[PayslipAlert]:
    """Le total imprimé d'une rubrique est la somme de ses lignes, pas le total stocké à côté."""
    alertes: list[PayslipAlert] = []
    for rubrique in payslip_data.get("cotisations_officielles") or []:
        if not isinstance(rubrique, dict):
            continue
        lignes = [ligne for ligne in rubrique.get("lignes") or [] if isinstance(ligne, dict)]
        if not lignes:
            continue
        nom = str(rubrique.get("libelle") or rubrique.get("code") or "Rubrique")
        for rule_id, cle, cote in (
            ("B03", "total_salarial", "salariale"),
            ("B04", "total_patronal", "patronale"),
        ):
            if cle not in rubrique:
                continue
            montant_cle = "montant_salarial" if cle == "total_salarial" else "montant_patronal"
            imprime = _nombre(rubrique.get(cle))
            rejoue = round(sum(_nombre(ligne.get(montant_cle)) for ligne in lignes), 2)
            ecart = round(imprime - rejoue, 2)
            if abs(ecart) <= 0.01:
                continue
            alertes.append(
                _alerte(
                    rule_id,
                    f"{rubrique.get('code') or nom}:{cle}",
                    imprime,
                    rejoue,
                    (
                        f"Le total {cote} de la rubrique « {nom} » est {_euros(imprime)}. "
                        f"La somme de ses lignes est {_euros(rejoue)} : {_sens(ecart)}."
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
