"""
Règles de calcul des augmentations de salaire.

Périmètres :
- brut_seul : augmentation sur la part base 35 h uniquement (HS structurelles inchangées)
- brut_et_hs : augmentation sur le salaire mensuel contractuel total
"""

from __future__ import annotations

from typing import Literal, TypedDict

DUREE_LEGALE_HEBDO = 35.0
# Majoration HS structurelle par défaut (1re tranche) si barèmes indisponibles.
MAJORATION_HS_DEFAUT = 0.25

TypeAugmentation = Literal["pourcentage", "montant_fixe"]
PerimetreAugmentation = Literal["brut_seul", "brut_et_hs"]


class DecompositionSalaire(TypedDict):
    salaire_contractuel: float
    base_35h: float
    part_hs: float
    duree_hebdomadaire: float
    a_hs_structurelles: bool


class ResultatAugmentation(TypedDict):
    ancien_salaire_brut: float
    nouveau_salaire_brut: float
    difference_brut: float
    taux_augmentation_reel: float
    ancien_base_35h: float
    ancien_part_hs: float
    nouveau_base_35h: float
    nouveau_part_hs: float
    a_hs_structurelles: bool
    perimetre_augmentation: PerimetreAugmentation


def _heures_mensuelles(duree_hebdo: float) -> float:
    return round((duree_hebdo * 52) / 12, 2)


def decomposer_salaire_contractuel(
    salaire_contractuel: float,
    duree_hebdomadaire: float | None,
    majoration_hs: float | None = None,
) -> DecompositionSalaire:
    """Découpe le salaire mensuel en base 35 h et HS structurelles (logique moteur paie)."""
    duree = float(duree_hebdomadaire or DUREE_LEGALE_HEBDO)
    if duree <= 0:
        duree = DUREE_LEGALE_HEBDO

    if duree <= DUREE_LEGALE_HEBDO:
        return DecompositionSalaire(
            salaire_contractuel=round(salaire_contractuel, 2),
            base_35h=round(salaire_contractuel, 2),
            part_hs=0.0,
            duree_hebdomadaire=duree,
            a_hs_structurelles=False,
        )

    maj = MAJORATION_HS_DEFAUT if majoration_hs is None else float(majoration_hs)
    heures_legales = _heures_mensuelles(DUREE_LEGALE_HEBDO)
    heures_hs = _heures_mensuelles(duree - DUREE_LEGALE_HEBDO)
    heures_equivalentes = heures_legales + (heures_hs * (1 + maj))
    taux_horaire = (
        salaire_contractuel / heures_equivalentes if heures_equivalentes > 0 else 0.0
    )
    base_35h = round(heures_legales * taux_horaire, 2)
    part_hs = round(salaire_contractuel - base_35h, 2)
    return DecompositionSalaire(
        salaire_contractuel=round(salaire_contractuel, 2),
        base_35h=base_35h,
        part_hs=part_hs,
        duree_hebdomadaire=duree,
        a_hs_structurelles=True,
    )


def _appliquer_sur_montant(
    montant: float,
    type_augmentation: TypeAugmentation,
    valeur: float,
) -> float:
    if type_augmentation == "pourcentage":
        return montant * (1 + valeur / 100)
    return montant + valeur


def calculer_nouveau_salaire_brut(
    salaire_contractuel: float,
    duree_hebdomadaire: float | None,
    type_augmentation: TypeAugmentation,
    valeur: float,
    perimetre: PerimetreAugmentation = "brut_et_hs",
    majoration_hs: float | None = None,
) -> ResultatAugmentation:
    """Calcule le nouveau salaire mensuel contractuel après augmentation."""
    deco = decomposer_salaire_contractuel(
        salaire_contractuel, duree_hebdomadaire, majoration_hs
    )
    ancien_total = deco["salaire_contractuel"]
    ancien_base = deco["base_35h"]
    ancien_hs = deco["part_hs"]

    if perimetre == "brut_seul" and deco["a_hs_structurelles"]:
        nouveau_base = _appliquer_sur_montant(ancien_base, type_augmentation, valeur)
        nouveau_total = round(nouveau_base + ancien_hs, 2)
        nouveau_hs = ancien_hs
    else:
        nouveau_total = round(
            _appliquer_sur_montant(ancien_total, type_augmentation, valeur), 2
        )
        nouveau_deco = decomposer_salaire_contractuel(
            nouveau_total, duree_hebdomadaire, majoration_hs
        )
        nouveau_base = nouveau_deco["base_35h"]
        nouveau_hs = nouveau_deco["part_hs"]

    diff = round(nouveau_total - ancien_total, 2)
    taux_reel = (diff / ancien_total * 100) if ancien_total > 0 else 0.0

    return ResultatAugmentation(
        ancien_salaire_brut=ancien_total,
        nouveau_salaire_brut=nouveau_total,
        difference_brut=diff,
        taux_augmentation_reel=round(taux_reel, 4),
        ancien_base_35h=ancien_base,
        ancien_part_hs=ancien_hs,
        nouveau_base_35h=round(nouveau_base, 2),
        nouveau_part_hs=round(nouveau_hs, 2),
        a_hs_structurelles=deco["a_hs_structurelles"],
        perimetre_augmentation=perimetre,
    )


def enrichir_salaire_avec_augmentation(
    salaire_dict: dict,
    type_augmentation: TypeAugmentation | None,
    valeur: float | None,
    perimetre: PerimetreAugmentation | None,
) -> dict:
    """Ajoute les métadonnées d'augmentation au dict salaire stocké en historique."""
    out = dict(salaire_dict)
    if type_augmentation and valeur is not None and perimetre:
        out["augmentation"] = {
            "type": type_augmentation,
            "valeur": valeur,
            "perimetre": perimetre,
        }
    return out


__all__ = [
    "DUREE_LEGALE_HEBDO",
    "MAJORATION_HS_DEFAUT",
    "TypeAugmentation",
    "PerimetreAugmentation",
    "DecompositionSalaire",
    "ResultatAugmentation",
    "decomposer_salaire_contractuel",
    "calculer_nouveau_salaire_brut",
    "enrichir_salaire_avec_augmentation",
]
