"""Valeurs proposées à la création d'un salarié : celles de la société.

La fenêtre de création proposait des valeurs génériques (salaire 2 365,66 €,
classification C / 6 / 240, titres-restaurant cochés, aucune mutuelle), fausses
pour Colorplast, et une mutuelle oubliée faisait un bulletin faux sans alerte.
On propose ce que portent déjà les salariés actifs de la société : durée,
convention, classification la plus courante, mutuelle obligatoire de la
catégorie, prévoyance, titres-restaurant, salaire saisi en base 35 h au-delà
de 35 h. Tout reste modifiable ; le salaire,
propre à chaque embauche, n'est jamais proposé.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

STATUTS_ACTIFS = frozenset({"actif", "active"})
NON_CADRE = "Non-Cadre"
CADRE = "Cadre"


def _est_cadre(statut: Any) -> bool:
    return str(statut or "").strip().lower() == "cadre"


def _le_plus_courant(valeurs: Iterable[Any]) -> Any:
    compte = Counter(v for v in valeurs if v not in (None, "", "Non précisé"))
    return compte.most_common(1)[0][0] if compte else None


def _entier(valeur: Any) -> int | None:
    try:
        return int(float(str(valeur)))
    except (TypeError, ValueError):
        return None


def _mutuelles_de_la_categorie(
    employes: list[dict[str, Any]], mutuelles: list[dict[str, Any]], cadre: bool
) -> list[str]:
    """Les mutuelles obligatoires que porte la majorité des salariés de la catégorie.

    Une option personnelle (complément famille, part salariale facultative) n'est
    jamais proposée : c'est un choix du salarié.
    """
    categorie = "cadre" if cadre else "non_cadre"
    eligibles = {
        str(m["id"])
        for m in mutuelles
        if m.get("is_active", True)
        and m.get("part_salariale_obligatoire", True)
        and str(m.get("statut_categoriel") or "tous") in (categorie, "tous")
    }
    groupe = [e for e in employes if _est_cadre(e.get("statut")) == cadre]
    if not groupe:
        exactes = [
            str(m["id"])
            for m in mutuelles
            if str(m["id"]) in eligibles and m.get("statut_categoriel") == categorie
        ]
        return exactes if len(exactes) == 1 else []
    usages = Counter(
        str(mid)
        for e in groupe
        for mid in (((e.get("specificites_paie") or {}).get("mutuelle") or {}).get("mutuelle_type_ids") or [])
    )
    return sorted(mid for mid, n in usages.items() if mid in eligibles and n * 2 > len(groupe))


def valeurs_d_embauche(
    employes: list[dict[str, Any]], mutuelles: list[dict[str, Any]]
) -> dict[str, Any]:
    actifs = [
        e for e in employes if str(e.get("employment_status") or "actif").lower() in STATUTS_ACTIFS
    ]
    non_cadres = [e for e in actifs if not _est_cadre(e.get("statut"))] or actifs
    classifications = [e.get("classification_conventionnelle") or {} for e in non_cadres]
    specificites = [e.get("specificites_paie") or {} for e in actifs]

    coefficient = _le_plus_courant(_entier(c.get("coefficient")) for c in classifications)
    classe = _le_plus_courant(_entier(c.get("classe_emploi")) for c in classifications)
    groupe = _le_plus_courant(str(c.get("groupe_emploi") or "").strip() for c in classifications)
    duree = _le_plus_courant(
        round(float(e["duree_hebdomadaire"]), 2) for e in non_cadres if e.get("duree_hebdomadaire")
    )
    prevoyances = [bool((s.get("prevoyance") or {}).get("adhesion")) for s in specificites]
    titres = [
        bool((s.get("titres_restaurant") or {}).get("beneficie"))
        and (_entier((s.get("titres_restaurant") or {}).get("nombre_par_mois")) or 0) > 0
        for s in specificites
    ]
    # Au-delà de 35 h, le salaire saisi est-il la base à 35 h (heures
    # structurelles payées en plus) ? Ce que fait la majorité des collègues :
    # sans cela, une base saisie au SMIC était payée sous le SMIC horaire.
    bases_35h = [
        bool((e.get("specificites_paie") or {}).get("salaire_hors_hs_structurelles"))
        for e in actifs
        if float(e.get("duree_hebdomadaire") or 0) > 35
    ]

    return {
        "statut": NON_CADRE,
        "contract_type": "CDI",
        "duree_hebdomadaire": duree,
        "collective_agreement_id": _le_plus_courant(
            str(e["collective_agreement_id"]) for e in actifs if e.get("collective_agreement_id")
        ),
        "classification_conventionnelle": (
            {
                "groupe_emploi": groupe or "",
                "classe_emploi": classe if classe is not None else coefficient,
                "coefficient": coefficient,
            }
            if coefficient
            else None
        ),
        "mutuelle_type_ids_par_statut": {
            NON_CADRE: _mutuelles_de_la_categorie(actifs, mutuelles, cadre=False),
            CADRE: _mutuelles_de_la_categorie(actifs, mutuelles, cadre=True),
        },
        "prevoyance_adhesion": (sum(prevoyances) * 2 >= len(prevoyances)) if prevoyances else True,
        "titres_restaurant_beneficie": (sum(titres) * 2 > len(titres)) if titres else False,
        "salaire_hors_hs_structurelles": (sum(bases_35h) * 2 > len(bases_35h)) if bases_35h else False,
    }
