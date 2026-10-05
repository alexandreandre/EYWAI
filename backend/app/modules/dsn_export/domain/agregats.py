"""Blocs de paiement de l'établissement : bordereau et cotisations agrégées
Urssaf (S21.G00.22 / 23), versements aux organismes (S21.G00.20).

Le bordereau se reconstruit depuis les cotisations individuelles (bloc 81)
déclarées à l'Urssaf : chaque code de cotisation rejoint son code type de
personnel (CTP) et son qualifiant d'assiette — 921 l'assiette plafonnée
(base 02), 920 toute autre assiette (guide déclaratif Urssaf). Tous les
montants agrégés s'arrondissent à l'euro (art. L130-1 CSS), assiette comme
cotisation, et le montant dû est la somme des cotisations de chaque CTP
arrondies à l'euro, réductions déduites.

La correspondance a été relevée sur les douze DSN 2026 de l'ancien logiciel
(Colorplast et Comitech, janvier à juin) : reconstruit depuis leurs propres
cotisations individuelles, le bordereau retombe à l'euro sur le leur six fois
sur douze, et les six autres s'expliquent (solde annuel de taxe
d'apprentissage en avril, CTP 995, et une réduction ponctuelle, CTP 478) —
ni l'un ni l'autre n'est une cotisation individuelle. Un code sans CTP connu
est signalé, jamais deviné.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Réductions déclarées en montant (23.005), assiette nulle.
CTP_REDUCTIONS = {"003", "004", "668"}
#: Régularisation positive de la réduction générale : déclarée en assiette.
CTP_REGULARISATION_REDUCTION = "669"
#: CTP dont le taux se déclare (23.003) : accident du travail et chômage modulé.
CTP_TAUX_DECLARE = {("100", "920"), ("725", "920")}

TAUX_CHOMAGE_DROIT_COMMUN = 4.0
TAUX_CFP_MOINS_DE_11 = 0.55


def _arrondi_euro(valeur: float) -> int:
    return int(Decimal(str(round(valeur, 6))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ctp_du_code(code: str, base: str, taux: float, montant: float = 0.0) -> Optional[Tuple[str, str]]:
    """(CTP, qualifiant d'assiette) d'une cotisation individuelle Urssaf."""
    if code in ("075", "074", "068", "045") or (code == "076" and base == "03"):
        return "100", "920"
    if code == "076" and base == "02":
        return "100", "921"
    if code in ("072", "073", "079"):
        return "260", "920"
    if code == "049":
        return ("332", "921") if base == "02" else ("236", "920")
    if code == "102":
        return "430", "920"
    if code == "907":
        return "635", "920"
    if code == "040":
        return ("772", "920") if abs(taux - TAUX_CHOMAGE_DROIT_COMMUN) < 1e-6 else ("725", "920")
    if code == "048":
        return "937", "920"
    if code == "128":
        return ("959", "920") if abs(taux - TAUX_CFP_MOINS_DE_11) < 1e-6 else ("971", "920")
    if code == "130":
        return "992", "920"
    if code == "100":
        return "027", "920"
    if code == "129":
        return "987", "920"
    if code == "071":
        return ("479", "920") if abs(taux - 8.0) < 1e-6 else ("012", "920")
    if code == "114":
        return "003", "921"
    if code == "021":
        return "004", "921"
    if code == "018":
        return ("669", "921") if montant > 0 else ("668", "921")
    return None


#: Codes déclarés avec l'OPS Urssaf mais hors bordereau : la part patronale
#: Agirc-Arrco (142, 146) sert au contrôle de la réduction générale.
CODES_HORS_BORDEREAU = {"142", "146"}


def bordereau_urssaf(
    salaries: Iterable[List[Dict[str, Any]]],
) -> Tuple[List[Dict[str, str]], int, List[str]]:
    """Cotisations agrégées (23), montant du bordereau (22.005) et codes inconnus.

    ``salaries`` : pour chaque salarié, ses cotisations individuelles Urssaf
    ``{code, base, assiette, montant, taux}`` (taux en pourcentage).
    """
    assiettes: Dict[Tuple[str, str], float] = {}
    montants: Dict[Tuple[str, str], float] = {}
    taux_declares: Dict[Tuple[str, str], str] = {}
    inconnus: List[str] = []
    for lignes in salaries:
        par_ctp: Dict[Tuple[str, str], float] = {}
        for ligne in lignes:
            code = str(ligne.get("code") or "")
            if code in CODES_HORS_BORDEREAU:
                continue
            taux = float(ligne.get("taux") or 0)
            montant = float(ligne.get("montant") or 0)
            assiette_ligne = float(ligne.get("assiette") or 0)
            if not taux and montant and assiette_ligne:
                # Taux absent (bulletin repris) : celui que donnent montant et
                # assiette, arrondi au centième de point.
                taux = round(abs(montant) / assiette_ligne * 100, 2)
            cle = ctp_du_code(code, str(ligne.get("base") or ""), taux, montant)
            if cle is None:
                if code not in inconnus:
                    inconnus.append(code)
                continue
            # Plusieurs codes du même CTP partagent l'assiette du salarié.
            par_ctp[cle] = max(par_ctp.get(cle, 0.0), float(ligne.get("assiette") or 0))
            montants[cle] = montants.get(cle, 0.0) + montant
            if cle in CTP_TAUX_DECLARE and (code == "045" or code == "040"):
                taux_declares[cle] = f"{taux:.2f}"
        for cle, assiette in par_ctp.items():
            assiettes[cle] = assiettes.get(cle, 0.0) + assiette

    lignes_23: List[Dict[str, str]] = []
    total = 0
    for cle in sorted(set(assiettes) | set(montants)):
        ctp, qualifiant = cle
        montant = montants.get(cle, 0.0)
        if ctp in CTP_REDUCTIONS:
            valeur = _arrondi_euro(abs(montant))
            total -= valeur
            lignes_23.append(
                {"ctp": ctp, "qualifiant": qualifiant, "taux": "", "assiette": "0.00", "montant": f"{valeur:.2f}"}
            )
            continue
        if ctp == CTP_REGULARISATION_REDUCTION:
            valeur = _arrondi_euro(montant)
            total += valeur
            lignes_23.append(
                {"ctp": ctp, "qualifiant": qualifiant, "taux": "", "assiette": f"{valeur:.2f}", "montant": "0.00"}
            )
            continue
        total += _arrondi_euro(montant)
        lignes_23.append(
            {
                "ctp": ctp,
                "qualifiant": qualifiant,
                "taux": taux_declares.get(cle, ""),
                "assiette": f"{_arrondi_euro(assiettes.get(cle, 0.0)):.2f}",
                "montant": "0.00",
            }
        )
    return lignes_23, total, inconnus


def montant_retraite_complementaire(salaries: Iterable[List[Dict[str, Any]]]) -> float:
    """Versement Agirc-Arrco : total (131), Apec (132) et réduction (106), au centime."""
    return round(
        sum(
            float(l.get("montant") or 0)
            for lignes in salaries
            for l in lignes
            if str(l.get("code") or "") in ("131", "132", "106")
        ),
        2,
    )
