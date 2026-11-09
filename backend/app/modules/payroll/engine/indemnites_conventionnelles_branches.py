"""Indemnités de rupture des conventions de branche, au-delà du licenciement.

Plasturgie (IDCC 0292) : avenant du 2 juillet 2020 relatif aux indemnités de
licenciement et de retraite, lu le 08/11/2026 dans sa reproduction
(presse.tripalio.fr, IDCC-292-Avenant-indemnite-de-licenciement.pdf) : Légifrance
refuse l'accès, le Code du travail numérique ne cite que le titre de l'avenant.
- art. 2 : licenciement, dès 8 mois ; coefficients 700 à 830, 1/4 de mois par
  année jusqu'à 10 ans, 1/3 au-delà (le barème légal) ; 900 et plus, 1/4 jusqu'à
  3 ans, puis 3/10 depuis l'entrée jusqu'à la 8e année, 4/10 de la 9e à la 13e,
  5/10 au-delà, 15 mois au plus ;
- art. 3 a : départ volontaire ; 700 à 830, la moitié de l'indemnité de
  licenciement, dans la limite de 30 ans ; 900 à 940, dès 5 ans, 0,15 mois par
  année jusqu'à la 8e, 0,2 de la 9e à la 13e, 0,25 au-delà, 7,5 mois au plus ;
- art. 3 b : mise à la retraite, le barème du licenciement, 15 mois au plus.
Chaque fois « plus avantageux » que la loi, sinon le minimum légal.

Métallurgie (IDCC 3248) : départ volontaire, art. 77.3, lu sur le Code du travail
numérique le 08/11/2026 (contribution 3248, départ à la retraite) : dès 2 ans,
0,5 mois ; 5 ans, 1 ; 10 ans, 2 ; 20 ans, 3 ; 30 ans, 4 ; 35 ans, 5 ; 40 ans, 6.
La mise à la retraite y renvoie au Code du travail : rien de plus à calculer.

Non calculé, et dit à l'écran : le salaire de référence de la plasturgie retient
aussi le dernier mois entier, et l'accord Seine et Seine-et-Oise donne 3/10 aux
collaborateurs d'Île-de-France.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

IDCC_PLASTURGIE = "0292"
COEFFICIENT_CADRE = 900.0
COEFFICIENT_MAXI_DEPART_CADRE = 940.0
PLAFOND_MOIS_LICENCIEMENT_CADRE = 15.0
PLAFOND_MOIS_DEPART_CADRE = 7.5
ANNEES_MAXI_DEPART_COLLABORATEUR = 30.0

#: Métallurgie, art. 77.3 : (années d'ancienneté minimales, mois de salaire).
BAREME_DEPART_METALLURGIE = ((40, 6.0), (35, 5.0), (30, 4.0), (20, 3.0), (10, 2.0), (5, 1.0), (2, 0.5))

ALERTE_SALAIRE_PLASTURGIE = (
    "Convention de la plasturgie : le salaire de référence retient aussi le dernier "
    "mois entier s'il est plus élevé que les moyennes sur 12 et 3 mois, ce que Martine "
    "ne calcule pas. Vérifiez-le et, s'il est plus favorable, saisissez le montant "
    "dans « Indemnité conventionnelle »."
)
ALERTE_SEINE = (
    "Convention de la plasturgie : l'accord Seine et Seine-et-Oise (Paris, Yvelines, "
    "Essonne, Hauts-de-Seine, Seine-Saint-Denis, Val-de-Marne, Val-d'Oise) donne 3/10 "
    "de mois par année après 5 ans aux collaborateurs : Martine ne le calcule pas, "
    "saisissez le montant dans « Indemnité conventionnelle »."
)


def _fr(montant: float) -> str:
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",") + " €"


def coefficient_de_la_fiche(classification: Any) -> Optional[float]:
    if not isinstance(classification, dict):
        return None
    try:
        return float(str(classification.get("coefficient")).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _est_cadre(coefficient: Optional[float], statut: Any) -> Optional[bool]:
    """Cadre ou collaborateur ; None si ni le coefficient ni le statut ne le disent."""
    if coefficient is not None:
        return coefficient >= COEFFICIENT_CADRE
    texte = str(statut or "").strip().lower()
    if not texte:
        return None
    return texte.startswith("cadre")


def _resultat(
    montant_mois: float, salaire: float, intitule: str, regle: str, mois_d_anciennete: int, alertes: list
) -> Dict[str, Any]:
    montant = round(salaire * montant_mois, 2)
    return {
        "montant": montant,
        "mois_de_salaire": round(montant_mois, 4),
        "calcul": (
            f"{intitule}, {mois_d_anciennete} mois d'ancienneté ({regle}) : "
            f"{round(montant_mois, 4)} mois × {_fr(salaire)} = {_fr(montant)}"
        ),
        "alertes": alertes,
    }


def _coefficient_inconnu() -> Dict[str, Any]:
    return {
        "montant": None,
        "calcul": "",
        "alertes": [
            "Convention de la plasturgie : ni le coefficient ni le statut du salarié ne "
            "sont renseignés, Martine ne peut pas calculer le minimum conventionnel. "
            "Complétez la fiche, ou saisissez le montant dans « Indemnité conventionnelle »."
        ],
    }


def _mois_licenciement_cadre(annees: float) -> tuple[float, str]:
    if annees <= 3:
        return annees / 4, "1/4 de mois par année jusqu'à 3 ans"
    mois = min(annees, 8) * 3 / 10 + max(0.0, min(annees, 13) - 8) * 4 / 10 + max(0.0, annees - 13) * 5 / 10
    regle = "3/10 de mois par année jusqu'à la 8e, 4/10 de la 9e à la 13e, 5/10 au-delà"
    if mois > PLAFOND_MOIS_LICENCIEMENT_CADRE:
        return PLAFOND_MOIS_LICENCIEMENT_CADRE, regle + " ; plafond de 15 mois"
    return mois, regle


def _mois_bareme_legal(annees: float) -> float:
    return min(annees, 10) / 4 + max(0.0, annees - 10) / 3


def indemnite_plasturgie_licenciement(
    *,
    coefficient: Optional[float],
    statut: Any,
    mois_d_anciennete: Optional[int],
    salaire_reference: float,
    intitule: str = "Convention de la plasturgie, licenciement",
) -> Optional[Dict[str, Any]]:
    """Licenciement, et mise à la retraite (même barème), ou None sous 8 mois."""
    if mois_d_anciennete is None or mois_d_anciennete < 8 or salaire_reference <= 0:
        return None
    cadre = _est_cadre(coefficient, statut)
    if cadre is None:
        return _coefficient_inconnu()
    annees = mois_d_anciennete / 12
    if cadre:
        mois, regle = _mois_licenciement_cadre(annees)
        return _resultat(mois, salaire_reference, f"{intitule}, cadre", regle, mois_d_anciennete, [ALERTE_SALAIRE_PLASTURGIE])
    return _resultat(
        _mois_bareme_legal(annees),
        salaire_reference,
        f"{intitule}, collaborateur",
        "1/4 de mois par année jusqu'à 10 ans, 1/3 au-delà : le barème légal",
        mois_d_anciennete,
        [ALERTE_SALAIRE_PLASTURGIE, ALERTE_SEINE],
    )


def indemnite_plasturgie_depart_retraite(
    *,
    coefficient: Optional[float],
    statut: Any,
    mois_d_anciennete: Optional[int],
    salaire_reference: float,
) -> Optional[Dict[str, Any]]:
    """Départ volontaire à la retraite, art. 29 bis a des clauses générales."""
    if mois_d_anciennete is None or salaire_reference <= 0:
        return None
    cadre = _est_cadre(coefficient, statut)
    if cadre is None:
        return _coefficient_inconnu()
    annees = mois_d_anciennete / 12
    intitule = "Convention de la plasturgie, départ à la retraite"
    if not cadre:
        if mois_d_anciennete < 8:
            return None
        retenues = min(annees, ANNEES_MAXI_DEPART_COLLABORATEUR)
        return _resultat(
            _mois_bareme_legal(retenues) / 2,
            salaire_reference,
            f"{intitule}, collaborateur",
            "moitié de l'indemnité de licenciement, dans la limite de 30 ans",
            mois_d_anciennete,
            [ALERTE_SALAIRE_PLASTURGIE],
        )
    if coefficient is not None and coefficient > COEFFICIENT_MAXI_DEPART_CADRE:
        return {
            "montant": None,
            "calcul": "",
            "alertes": [
                f"Convention de la plasturgie : le barème de départ à la retraite des cadres "
                f"s'arrête au coefficient 940 (fiche : {coefficient:g}). Saisissez le montant "
                "dans « Indemnité conventionnelle »."
            ],
        }
    if annees < 5:
        return None
    mois = min(annees, 8) * 0.15 + max(0.0, min(annees, 13) - 8) * 0.2 + max(0.0, annees - 13) * 0.25
    regle = "0,15 mois par année jusqu'à la 8e, 0,2 de la 9e à la 13e, 0,25 au-delà"
    if mois > PLAFOND_MOIS_DEPART_CADRE:
        mois = PLAFOND_MOIS_DEPART_CADRE
        regle += " ; plafond de 7,5 mois"
    return _resultat(mois, salaire_reference, f"{intitule}, cadre", regle, mois_d_anciennete, [ALERTE_SALAIRE_PLASTURGIE])


def indemnite_metallurgie_depart_retraite(
    *, mois_d_anciennete: Optional[int], salaire_reference: float
) -> Optional[Dict[str, Any]]:
    """Départ volontaire à la retraite, métallurgie, art. 77.3."""
    if mois_d_anciennete is None or salaire_reference <= 0:
        return None
    annees = mois_d_anciennete // 12
    mois = next((m for seuil, m in BAREME_DEPART_METALLURGIE if annees >= seuil), 0.0)
    if not mois:
        return None
    return _resultat(
        mois,
        salaire_reference,
        "Convention de la métallurgie, départ à la retraite",
        f"art. 77.3 : {mois:g} mois pour {annees} ans".replace(".", ","),
        mois_d_anciennete,
        [],
    )
