"""Indemnité de congés payés de fin de CDD : la méthode se choisit par société.

Par défaut, le dixième légal de la rémunération réellement versée pendant le
contrat, précarité comprise (`calcul_brut._calculer_iccp_cdd`). La méthode
« salaire rétabli du mois de sortie, congés N-1 inclus » — décision
d'Alexandre du 21/09/2026 pour Colorplast, spec
2026-09-21-indemnite-cp-fin-cdd-methode-design.md — élargit l'assiette :

- le sous-total salaire contractuel du dernier mois est remplacé par celui du
  mois plein (heures mensuelles légales × taux + HS structurelles majorées) ;
  les autres éléments du mois restent ;
- le solde de congés N-1 restant à la fin du mois est valorisé à la valeur
  d'un jour au maintien, la même que celle qui paie un jour de congé.

Recette : Aurélien Demory, juillet 2026 — 6 197,76 + 2 133,73 + 797,04 +
2,78 j × 98,48 = 9 402,30 ; × 10 % = 940,23, le bulletin Quadra au centime.
Ce module ne lit ni base ni fichier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import legal_constants as lc
from .iccp_arbitrage import calculer_maintien_horaire
from .salaire_contractuel import heures_sup_structurelles_mensuelles

CLE_PARAMETRE = "indemnite_cp_fin_cdd"
METHODE_PAR_DEFAUT = "remuneration_versee"
METHODE_SALAIRE_RETABLI = "salaire_retabli_solde_n1"
METHODES = (METHODE_PAR_DEFAUT, METHODE_SALAIRE_RETABLI)


def methode_depuis_parametres(entreprise: Mapping[str, Any] | None) -> str:
    """La méthode se lit dans `entreprise.parametres_paie` ; inconnue ou absente = défaut."""
    parametres = (entreprise or {}).get("parametres_paie") or {}
    valeur = parametres.get(CLE_PARAMETRE)
    return valeur if valeur in METHODES else METHODE_PAR_DEFAUT


def heures_mensuelles_legales() -> float:
    return round(lc.DUREE_LEGALE_HEBDO * 52 / 12, 2)


def salaire_retabli_du_mois(
    taux_horaire_base: float, duree_hebdo: float, majoration_hs25: float
) -> float:
    """Le salaire contractuel d'un mois plein : base légale + HS structurelles majorées."""
    base = round(heures_mensuelles_legales() * taux_horaire_base, 2)
    heures_structurelles = heures_sup_structurelles_mensuelles(duree_hebdo)
    structurelles = (
        round(heures_structurelles * taux_horaire_base * (1 + majoration_hs25), 2)
        if heures_structurelles > 0
        else 0.0
    )
    return round(base + structurelles, 2)


def valeur_jour_maintien(
    taux_horaire_base: float, duree_hebdo: float, majoration_hs25: float
) -> float:
    """Ce que vaut un jour de congé au maintien : la règle de `calcul_conges`."""
    heures_normales = min(duree_hebdo, lc.DUREE_LEGALE_HEBDO) / 5
    heures_structurelles = max(0.0, (duree_hebdo - lc.DUREE_LEGALE_HEBDO) / 5)
    return calculer_maintien_horaire(
        1.0,
        taux_horaire_base,
        heures_normales_par_jour=heures_normales,
        heures_supp_par_jour=heures_structurelles,
        majoration_hs=majoration_hs25,
    ).total


@dataclass(frozen=True)
class AssietteSalaireRetabli:
    cumul_brut_contrat: float
    brut_du_mois: float
    sous_total_contractuel_reel: float
    salaire_retabli: float
    precarite: float
    solde_n1_jours: float
    valeur_jour: float

    @property
    def mois_retabli(self) -> float:
        """Le mois de sortie, sa part contractuelle remplacée par celle du mois plein."""
        return round(self.brut_du_mois - self.sous_total_contractuel_reel + self.salaire_retabli, 2)

    @property
    def solde_n1_valorise(self) -> float:
        if self.solde_n1_jours <= 0:
            return 0.0
        return round(self.solde_n1_jours * self.valeur_jour, 2)

    @property
    def total(self) -> float:
        return round(
            self.cumul_brut_contrat + self.mois_retabli + self.precarite + self.solde_n1_valorise,
            2,
        )

    def resume(self, taux: float, montant: float) -> dict[str, Any]:
        return {
            "methode": METHODE_SALAIRE_RETABLI,
            "cumul_brut_contrat": round(self.cumul_brut_contrat, 2),
            "mois_retabli": self.mois_retabli,
            "salaire_retabli": round(self.salaire_retabli, 2),
            "sous_total_contractuel_reel": round(self.sous_total_contractuel_reel, 2),
            "precarite": round(self.precarite, 2),
            "solde_n1_jours": round(self.solde_n1_jours, 2),
            "valeur_jour": round(self.valeur_jour, 2),
            "solde_n1_valorise": self.solde_n1_valorise,
            "assiette": self.total,
            "taux": taux,
            "montant": round(montant, 2),
            "mention": mention(self, taux=taux, montant=montant),
        }


def assiette_salaire_retabli(
    *,
    cumul_brut_contrat: float,
    brut_du_mois: float,
    sous_total_contractuel_reel: float,
    salaire_retabli: float,
    precarite: float,
    solde_n1_jours: float,
    valeur_jour: float,
) -> AssietteSalaireRetabli:
    return AssietteSalaireRetabli(
        cumul_brut_contrat=float(cumul_brut_contrat or 0.0),
        brut_du_mois=float(brut_du_mois or 0.0),
        sous_total_contractuel_reel=float(sous_total_contractuel_reel or 0.0),
        salaire_retabli=float(salaire_retabli or 0.0),
        precarite=max(float(precarite or 0.0), 0.0),
        solde_n1_jours=float(solde_n1_jours or 0.0),
        valeur_jour=float(valeur_jour or 0.0),
    )


def _euros(valeur: float) -> str:
    return f"{valeur:,.2f}".replace(",", " ").replace(".", ",")


def _nombre(valeur: float) -> str:
    return f"{valeur:.2f}".rstrip("0").rstrip(".").replace(".", ",") or "0"


def mention(assiette: AssietteSalaireRetabli, *, taux: float, montant: float) -> str:
    """La phrase du bulletin : les briques de l'assiette, le taux, le montant."""
    briques = [
        f"{_euros(assiette.cumul_brut_contrat)} (brut du contrat avant le mois)",
        f"{_euros(assiette.mois_retabli)} (mois de sortie rétabli)",
        f"{_euros(assiette.precarite)} (précarité)",
    ]
    if assiette.solde_n1_valorise > 0:
        briques.append(
            f"{_euros(assiette.solde_n1_valorise)} (solde N-1 : "
            f"{_nombre(assiette.solde_n1_jours)} j × {_euros(assiette.valeur_jour)})"
        )
    return (
        "Indemnité de congés payés de fin de CDD (méthode société : salaire rétabli du mois "
        "de sortie, congés N-1 inclus) : "
        + " + ".join(briques)
        + f" = {_euros(assiette.total)} × {taux * 100:g} % = {_euros(montant)}."
    )


__all__ = [
    "CLE_PARAMETRE",
    "METHODES",
    "METHODE_PAR_DEFAUT",
    "METHODE_SALAIRE_RETABLI",
    "AssietteSalaireRetabli",
    "assiette_salaire_retabli",
    "heures_mensuelles_legales",
    "mention",
    "methode_depuis_parametres",
    "salaire_retabli_du_mois",
    "valeur_jour_maintien",
]
