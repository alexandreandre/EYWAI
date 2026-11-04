"""Indemnité de licenciement de la métallurgie : le plancher de la convention.

CCN de la métallurgie du 7 février 2022 (IDCC 3248, étendue par arrêté du
14/12/2022, en vigueur étendu depuis le 01/01/2024 ; Légifrance, articles ouverts
le 04/11/2026) :
- art. 75.3 : due dès 8 mois d'ancienneté, sauf faute grave ou lourde ;
- art. 75.3.1.1, groupes d'emplois A à E : 1/4 de mois de salaire de référence
  par année jusqu'à 10 ans, 1/3 à partir de 10 ans ;
- art. 75.3.1.2, groupes F à I : moins de 8 ans, 1/4 de mois par année ; à
  partir de 8 ans, 1/5 de mois par année jusqu'à 7 ans et 3/5 à partir de
  7 ans ; jamais plus de 18 mois de salaire de référence. Dans les deux cas,
  les mois complets au-delà des années entières comptent pour 1/12 d'année ;
- art. 75.3.2 : salaire de référence, le plus avantageux des 12 ou 3 derniers
  mois (la règle du Code du travail, déjà appliquée) ;
- art. 75.3.3, groupes F à I : de 50 à moins de 55 ans, avec 5 ans
  d'ancienneté, majoration de 20 % et au moins 3 mois ; de 55 à moins de
  60 ans, 30 % et au moins 6 mois ; toujours 18 mois au plus. La minoration
  de 61 ans et plus ne s'applique pas si le salarié prouve qu'il n'a pas une
  retraite à taux plein : Martine ne la pose pas, elle le signale ;
- art. 76.2 : l'indemnité spécifique de rupture conventionnelle « est au moins
  égale à l'indemnité de licenciement prévue par l'article 75.3 ».

Audit du 03/11/2026 (lot F, verdict 1) : une rupture conventionnelle d'un cadre
du groupe F, 15 ans et 5 mois d'ancienneté, payée au minimum légal
(18 379,00 €) au lieu de 27 412,50 €.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

IDCC_METALLURGIE = "3248"
GROUPES_A_E = frozenset("ABCDE")
GROUPES_F_I = frozenset("FGHI")
PLAFOND_MOIS_F_I = 18.0


def groupe_d_emplois(classification: Any) -> str:
    """La lettre du groupe d'emplois de la classification (« F », « 11 F »), ou « »."""
    if not isinstance(classification, dict):
        return ""
    for cle in ("groupe_emploi", "groupe", "niveau_dsn"):
        texte = str(classification.get(cle) or "").strip().upper()
        for morceau in reversed(texte.split()):
            if len(morceau) == 1 and morceau in GROUPES_A_E | GROUPES_F_I:
                return morceau
    return ""


def _fr(montant: float) -> str:
    return f"{montant:,.2f}".replace(",", " ").replace(".", ",") + " €"


def indemnite_licenciement_metallurgie(
    *,
    groupe: str,
    mois_d_anciennete: Optional[int],
    salaire_reference: float,
    age: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Le plancher conventionnel (montant, mois de salaire, calcul, alertes), ou
    None si la convention ne le fixe pas (moins de 8 mois, groupe inconnu)."""
    if mois_d_anciennete is None or mois_d_anciennete < 8 or salaire_reference <= 0:
        return None
    groupe = (groupe or "").strip().upper()
    annees = mois_d_anciennete / 12
    alertes: list[str] = []
    if groupe in GROUPES_A_E:
        mois = min(annees, 10) / 4 + max(0.0, annees - 10) / 3
        regle = "art. 75.3.1.1 : 1/4 de mois par année jusqu'à 10 ans, 1/3 au-delà"
    elif groupe in GROUPES_F_I:
        if annees < 8:
            mois = annees / 4
            regle = "art. 75.3.1.2 : moins de 8 ans, 1/4 de mois par année"
        else:
            mois = min(annees, 7) / 5 + max(0.0, annees - 7) * 3 / 5
            regle = "art. 75.3.1.2 : 1/5 de mois par année jusqu'à 7 ans, 3/5 au-delà"
        if age is not None and annees >= 5:
            if 50 <= age < 55:
                mois = max(mois * 1.20, 3.0)
                regle += " ; art. 75.3.3 : 50 à 54 ans, +20 %, au moins 3 mois"
            elif 55 <= age < 60:
                mois = max(mois * 1.30, 6.0)
                regle += " ; art. 75.3.3 : 55 à 59 ans, +30 %, au moins 6 mois"
        if age is not None and age >= 61:
            alertes.append(
                "Convention de la métallurgie, art. 75.3.3 : à partir de 61 ans, "
                "l'indemnité peut être minorée, sauf si le salarié prouve qu'il n'a pas "
                "une retraite à taux plein. Martine ne la minore pas : vérifiez sa "
                "situation avant de baisser le montant."
            )
        if mois > PLAFOND_MOIS_F_I:
            mois = PLAFOND_MOIS_F_I
            regle += " ; plafond de 18 mois"
    else:
        return None
    montant = round(salaire_reference * mois, 2)
    return {
        "montant": montant,
        "mois_de_salaire": round(mois, 4),
        "groupe": groupe,
        "calcul": (
            f"Convention de la métallurgie, groupe {groupe}, {mois_d_anciennete} mois "
            f"d'ancienneté ({regle}) : {round(mois, 4)} mois × {_fr(salaire_reference)} "
            f"= {_fr(montant)}"
        ),
        "alertes": alertes,
    }
