"""Bloc S21.G00.56 : régulariser le prélèvement à la source d'un mois passé (R-173).

Fiche du bloc, cahier technique 2026.1 (ouverte le 08/11/2026). Ce module met en
forme et contrôle ce qu'on lui donne ; il ne calcule pas l'écart. Aucune saisie
n'alimente encore `regularisations_pas` : qui la pose, et où, reste à décider.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from app.modules.payroll.domain.report_nap_negatif import mois_en_lettres

_CLES = {
    "003": "regul_net_fiscal",
    "004": "net_fiscal_declare",
    "005": "regul_taux",
    "006": "taux_declare",
    "007": "montant_regul_pas",
    "008": "regul_part_non_imposable",
    "009": "regul_abattement",
    "010": "regul_montant_soumis",
    "015": "montant_soumis_declare",
}
_POSITIFS = ("006", "015")

#: CCH-11, 12, 13 et 26 de S21.G00.56.002 ; le montant (007) est présent partout.
_OBLIGATOIRES = {
    "01": ("003", "006", "007", "010"),
    "02": ("005", "007", "015"),
    "03": ("003", "006", "007", "010"),
    "04": ("003", "007", "010"),
}
#: CCH-15 et 18 de S21.G00.56.002.
_INTERDITES = {
    "01": ("004", "005", "015"),
    "02": ("003", "006", "008", "009", "010"),
    "03": ("004", "005", "015"),
    "04": ("004", "005", "015"),
}
_RE_MOIS = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")


class _Refus(ValueError):
    pass


def _rubrique(numero: str) -> str:
    return f"S21.G00.56.{numero}"


def _valeur(numero: str, brut: Any) -> str:
    try:
        nombre = Decimal(str(brut)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise _Refus(f"{_rubrique(numero)} n'est pas un nombre ({brut!r})") from exc
    if numero in _POSITIFS and nombre < 0:
        raise _Refus(f"{_rubrique(numero)} ne peut pas être négatif")
    if numero == "005" and nombre == 0:
        raise _Refus(f"{_rubrique(numero)} : un écart de taux nul ne se déclare pas")
    return f"{nombre:.2f}"


def _controler_le_mois(annee: int, mois: int, type_erreur: str, period: str) -> None:
    annee_dsn, mois_dsn = int(period[:4]), int(period[5:7])
    if (annee, mois) > (annee_dsn, mois_dsn):
        raise _Refus("le mois de l'erreur est postérieur au mois déclaré")  # CCH-11
    if type_erreur not in ("01", "02"):
        return
    if mois_dsn == 1 and annee != annee_dsn - 1:  # CCH-17
        raise _Refus("en janvier, seule l'année précédente se régularise")
    if mois_dsn != 1 and annee < annee_dsn:  # CCH-16
        raise _Refus("une année fiscale passée ne se régularise qu'en janvier")


def _bloc(regul: Mapping[str, Any], period: str) -> Dict[str, str]:
    trouve = _RE_MOIS.fullmatch(str(regul.get("mois_erreur") or ""))
    if trouve is None:
        raise _Refus(f"mois de l'erreur illisible ({regul.get('mois_erreur')!r})")
    annee, mois = int(trouve.group(1)), int(trouve.group(2))
    type_erreur = str(regul.get("type_erreur") or "")
    if type_erreur not in _OBLIGATOIRES:
        raise _Refus(f"type d'erreur inconnu ({type_erreur!r})")
    _controler_le_mois(annee, mois, type_erreur, period)

    presentes = {
        numero: regul[cle] for numero, cle in _CLES.items() if regul.get(cle) is not None
    }
    for numero in _OBLIGATOIRES[type_erreur]:
        if numero not in presentes:
            raise _Refus(f"{_rubrique(numero)} manque pour le type {type_erreur}")
    for numero in _INTERDITES[type_erreur]:
        if numero in presentes:
            raise _Refus(f"{_rubrique(numero)} est interdite pour le type {type_erreur}")

    valeurs = {numero: _valeur(numero, brut) for numero, brut in presentes.items()}
    if "008" in valeurs and not {"003", "010"} <= set(valeurs):  # CCH-11 de 56.008
        raise _Refus(f"{_rubrique('008')} exige {_rubrique('003')} et {_rubrique('010')}")
    if type_erreur == "03" and any(Decimal(valeurs[n]) > 0 for n in ("003", "010")):  # CCH-14
        raise _Refus("le cas d'indu porte des écarts négatifs ou nuls")
    if type_erreur == "04" and Decimal(valeurs["007"]) != 0:  # CCH-27
        raise _Refus(f"{_rubrique('007')} vaut 0.00 pour le type 04")

    return {
        _rubrique("001"): f"{mois:02d}{annee}",
        _rubrique("002"): type_erreur,
        **{_rubrique(numero): valeur for numero, valeur in valeurs.items()},
    }


def blocs_regularisation_pas(
    regularisations: Optional[Sequence[Mapping[str, Any]]], period: str
) -> Tuple[List[Dict[str, str]], List[str]]:
    """Les blocs à écrire, et pourquoi les autres ne le sont pas."""
    blocs: List[Dict[str, str]] = []
    erreurs: List[str] = []
    for regul in regularisations or []:
        try:
            blocs.append(_bloc(regul, period))
        except _Refus as exc:
            trouve = _RE_MOIS.fullmatch(str(regul.get("mois_erreur") or ""))
            quand = (
                f"de {mois_en_lettres(int(trouve.group(1)), int(trouve.group(2)))}" if trouve else ""
            )
            erreurs.append(f"Régularisation de PAS {quand} non déclarée : {exc}.".replace("  ", " "))
    return blocs, erreurs


def avis_versement_dgfip(blocs: Sequence[Mapping[str, str]]) -> str:
    total = sum(Decimal(b[_rubrique("007")]) for b in blocs)
    return (
        f"Régularisation de PAS déclarée ({total:.2f} €) : le versement à la DGFiP ne reprend "
        "que le PAS du mois. Vérifiez le montant à reverser avant de déposer."
    )
