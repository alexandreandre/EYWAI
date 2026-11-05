"""Attestation de salaire : les mois repris des bulletins remis (décision du 05/11/2026).

On ne prend que des bulletins déjà remis au salarié : la lettre dit la même
chose que ses bulletins, et Martine n'atteste jamais un brouillon. Les montants
sont ceux du bulletin : le salaire brut, et la ligne « Net à payer avant impôt
sur le revenu » (synthese_net.net_social_avant_impot). Le net payé dépend du
taux de prélèvement et des retenues, le net imposable sert à l'impôt : ni la
banque ni le bailleur n'en ont besoin.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

NOMBRE_DE_MOIS_PAR_DEFAUT = 3


def _montant(valeur: Any) -> float | None:
    if valeur is None or valeur == "":
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _ajouter(cumul: float | None, montant: float | None) -> float | None:
    """Un montant absent rend la somme inconnue : rien n'est inventé."""
    if cumul is None or montant is None:
        return None
    return cumul + montant


def mois_a_attester(
    bulletins: Iterable[Mapping[str, Any]], nombre: int
) -> list[dict[str, Any]]:
    """Les `nombre` mois les plus récents, du plus ancien au plus récent.

    `bulletins` : des bulletins déjà remis. Deux bulletins le même mois (un par
    contrat) font une seule ligne, montants additionnés.
    """
    par_mois: dict[tuple[int, int], dict[str, Any]] = {}
    for bulletin in bulletins:
        cle = (int(bulletin["year"]), int(bulletin["month"]))
        donnees = bulletin.get("payslip_data")
        donnees = donnees if isinstance(donnees, Mapping) else {}
        synthese = donnees.get("synthese_net")
        synthese = synthese if isinstance(synthese, Mapping) else {}
        ligne = par_mois.setdefault(
            cle, {"year": cle[0], "month": cle[1], "brut": 0.0, "net_avant_impot": 0.0}
        )
        ligne["brut"] = _ajouter(ligne["brut"], _montant(donnees.get("salaire_brut")))
        ligne["net_avant_impot"] = _ajouter(
            ligne["net_avant_impot"], _montant(synthese.get("net_social_avant_impot"))
        )

    retenus = sorted(par_mois)[-nombre:] if nombre > 0 else []
    return [
        {
            **par_mois[cle],
            "brut": _arrondi(par_mois[cle]["brut"]),
            "net_avant_impot": _arrondi(par_mois[cle]["net_avant_impot"]),
        }
        for cle in retenus
    ]


def _arrondi(montant: float | None) -> float | None:
    return None if montant is None else round(montant, 2)


def total(lignes: list[Mapping[str, Any]], cle: str) -> float | None:
    """La somme d'une colonne ; inconnue si une ligne l'est, ou s'il n'y a rien."""
    valeurs = [ligne.get(cle) for ligne in lignes]
    if not valeurs or any(valeur is None for valeur in valeurs):
        return None
    return round(sum(valeurs), 2)
