"""Formules de prévoyance de la société : copie sur la fiche (02/11/2026).

Une formule porte les lignes qu'on taperait sur la fiche (libellé, taux
salarial, patronal et de forfait social en fraction, base facultative). La
choisir les COPIE dans `specificites_paie.prevoyance.lignes_specifiques`, la
seule chose que lit le moteur, et pose `formule_id` pour savoir d'où elles
viennent. Aucune autre clé de la prévoyance ne bouge.
"""

from __future__ import annotations

import copy
from collections.abc import Iterable, Mapping
from typing import Any

#: La base que le moteur prend quand une ligne n'en dit rien
#: (`calcul_cotisations._sommer_part_patronale_lignes_taux`).
BASE_PAR_DEFAUT = "brut_plafonne"
_TAUX = ("salarial", "patronal", "forfait_social")


def appliquer_formule(prevoyance: Mapping[str, Any] | None, formule: Mapping[str, Any]) -> dict[str, Any]:
    """La prévoyance de la fiche avec les lignes de la formule (copie, entrées intactes)."""
    resultat = copy.deepcopy(dict(prevoyance or {}))
    resultat.setdefault("adhesion", True)
    lignes = []
    for rang, ligne in enumerate(formule.get("lignes") or [], start=1):
        copie = copy.deepcopy(dict(ligne))
        copie["id"] = f"prevoyance_{rang}"
        lignes.append(copie)
    resultat["lignes_specifiques"] = lignes
    resultat["formule_id"] = str(formule["id"])
    return resultat


def _taux(valeur: Any) -> float:
    try:
        return round(float(valeur or 0), 8)
    except (TypeError, ValueError):
        return float("nan")


def _cle(ligne: Mapping[str, Any]) -> tuple:
    autres = tuple(
        sorted(
            (k, repr(v))
            for k, v in ligne.items()
            if k not in {"id", "base", "libelle", *_TAUX}
        )
    )
    return (
        str(ligne.get("libelle") or "").strip(),
        *(_taux(ligne.get(t)) for t in _TAUX),
        str(ligne.get("base") or BASE_PAR_DEFAUT),
        autres,
    )


def lignes_identiques(a: Iterable[Mapping[str, Any]] | None, b: Iterable[Mapping[str, Any]] | None) -> bool:
    """Mêmes lignes, dans le même ordre, sans tenir compte des identifiants."""
    return [_cle(l) for l in (a or [])] == [_cle(l) for l in (b or [])]


def fiche_a_mettre_a_jour(specificites: Mapping[str, Any] | None, formule: Mapping[str, Any]) -> bool:
    """La fiche porte cette formule mais plus ses lignes."""
    prevoyance = (specificites or {}).get("prevoyance")
    if not isinstance(prevoyance, Mapping) or str(prevoyance.get("formule_id") or "") != str(formule["id"]):
        return False
    return not lignes_identiques(prevoyance.get("lignes_specifiques"), formule.get("lignes"))


def formule_convient(formule: Mapping[str, Any], cadre: bool) -> bool:
    categorie = formule.get("statut_categoriel") or "tous"
    return categorie == "tous" or (categorie == "cadre") == cadre
