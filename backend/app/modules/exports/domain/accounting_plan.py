"""Référentiel comptable paie — rattachement des cotisations aux organismes.

Le rattachement se fait sur `coti_id`, identifiant stable porté par chaque ligne
de cotisation du bulletin. Le libellé n'est utilisé qu'en dernier recours, pour
les rares lignes qui n'en portent pas (CSG sur participation).

Les comptes définis ici sont des défauts au plan comptable général. Chaque
société les surcharge en base (`accounting_mappings`) avec les comptes de son
cabinet — souvent à 8 chiffres et ventilés par organisme nommé.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

ORGANISME_URSSAF = "URSSAF"
ORGANISME_RETRAITE = "RETRAITE"
ORGANISME_RETRAITE_SUP = "RETRAITE_SUP"
ORGANISME_MUTUELLE = "MUTUELLE"
ORGANISME_PREVOYANCE = "PREVOYANCE"
ORGANISME_INCONNU = "INCONNU"

ORGANISMES: Dict[str, str] = {
    ORGANISME_URSSAF: "URSSAF",
    ORGANISME_RETRAITE: "Retraite complémentaire",
    ORGANISME_RETRAITE_SUP: "Retraite supplémentaire",
    ORGANISME_MUTUELLE: "Mutuelle",
    ORGANISME_PREVOYANCE: "Prévoyance",
    ORGANISME_INCONNU: "Organisme non rattaché",
}


@dataclass(frozen=True)
class AccountPair:
    """Couple de comptes d'un organisme : charge patronale et dette."""

    compte_charge: str
    compte_tiers: str


# coti_id → organisme. Recensé sur les bulletins de production de juin 2026.
COTI_TO_ORGANISME: Dict[str, str] = {
    # --- Recouvré par l'URSSAF ---
    "securite_sociale_maladie": ORGANISME_URSSAF,
    "allocations_familiales": ORGANISME_URSSAF,
    "assurance_chomage": ORGANISME_URSSAF,
    "ags": ORGANISME_URSSAF,
    "at_mp": ORGANISME_URSSAF,
    "retraite_secu_plafond": ORGANISME_URSSAF,
    "retraite_secu_deplafond": ORGANISME_URSSAF,
    "csg_deductible": ORGANISME_URSSAF,
    "csg_non_deductible": ORGANISME_URSSAF,
    "csa": ORGANISME_URSSAF,
    "fnal": ORGANISME_URSSAF,
    "dialogue_social": ORGANISME_URSSAF,
    "versement_mobilite": ORGANISME_URSSAF,
    "CFP": ORGANISME_URSSAF,
    "taxe_apprentissage": ORGANISME_URSSAF,
    "taxe_apprentissage_solde": ORGANISME_URSSAF,
    "forfait_social": ORGANISME_URSSAF,
    # Allègements et exonérations : même organisme, montant négatif
    "reduction_generale": ORGANISME_URSSAF,
    "deduction_hs_patronale": ORGANISME_URSSAF,
    "reduction_hs_salariale": ORGANISME_URSSAF,
    "exoneration_apprenti_salariale": ORGANISME_URSSAF,
    # --- Retraite complémentaire (AGIRC-ARRCO) ---
    "retraite_comp_t1": ORGANISME_RETRAITE,
    "retraite_comp_t2": ORGANISME_RETRAITE,
    "ceg_t1": ORGANISME_RETRAITE,
    "ceg_t2": ORGANISME_RETRAITE,
    "cet": ORGANISME_RETRAITE,
    "apec": ORGANISME_RETRAITE,
    # --- Retraite supplémentaire ---
    "retraite_sup": ORGANISME_RETRAITE_SUP,
    # --- Santé et prévoyance ---
    "mutuelle": ORGANISME_MUTUELLE,
    "prevoyance_cadre": ORGANISME_PREVOYANCE,
    "prevoyance_non_cadre": ORGANISME_PREVOYANCE,
}

# Comptes par défaut au PCG. Surchargés par société en base.
DEFAULT_ACCOUNTS: Dict[str, AccountPair] = {
    ORGANISME_URSSAF: AccountPair(compte_charge="645100", compte_tiers="431000"),
    ORGANISME_RETRAITE: AccountPair(compte_charge="645300", compte_tiers="437200"),
    ORGANISME_RETRAITE_SUP: AccountPair(compte_charge="645301", compte_tiers="437800"),
    ORGANISME_MUTUELLE: AccountPair(compte_charge="645242", compte_tiers="437020"),
    ORGANISME_PREVOYANCE: AccountPair(compte_charge="645241", compte_tiers="437400"),
}

# Éléments du bulletin qui ne sont pas des cotisations.
# Un compte vide signifie que l'élément n'a pas de compte de ce côté.
ELEMENT_ACCOUNTS: Dict[str, AccountPair] = {
    "salaire_brut": AccountPair(compte_charge="641000", compte_tiers=""),
    "prime_soumise": AccountPair(compte_charge="641100", compte_tiers=""),
    # 421 « Personnel — rémunérations dues », et non 425 « avances et acomptes »
    "net_a_payer": AccountPair(compte_charge="", compte_tiers="421000"),
    "pas": AccountPair(compte_charge="", compte_tiers="442000"),
    "saisie_opposition": AccountPair(compte_charge="", compte_tiers="427000"),
    "acompte": AccountPair(compte_charge="", compte_tiers="425000"),
    "avance": AccountPair(compte_charge="", compte_tiers="425200"),
    "pret_employeur": AccountPair(compte_charge="", compte_tiers="274000"),
    "note_de_frais": AccountPair(compte_charge="", compte_tiers="428625"),
    "indemnite_transport": AccountPair(compte_charge="648000", compte_tiers=""),
    "indemnite_de_transport": AccountPair(compte_charge="648000", compte_tiers=""),
}

# Repli par libellé, pour les lignes sans coti_id.
_LIBELLE_FALLBACK = (
    ("CSG", ORGANISME_URSSAF),
    ("CRDS", ORGANISME_URSSAF),
    ("URSSAF", ORGANISME_URSSAF),
    ("AGIRC", ORGANISME_RETRAITE),
    ("ARRCO", ORGANISME_RETRAITE),
    ("RETRAITE SUPP", ORGANISME_RETRAITE_SUP),
    ("RETRAITE", ORGANISME_RETRAITE),
    ("PREVOYANCE", ORGANISME_PREVOYANCE),
    ("PRÉVOYANCE", ORGANISME_PREVOYANCE),
    ("MUTUELLE", ORGANISME_MUTUELLE),
)


def resolve_organisme_from_coti_id(
    coti_id: Optional[str], libelle: str = ""
) -> str:
    """Rattache une ligne de cotisation à son organisme.

    `coti_id` prime toujours. Le libellé n'est consulté que si l'identifiant est
    absent — cas de la CSG sur participation, observé en production.
    Retourne `INCONNU` si rien ne correspond : l'appelant doit le signaler, pas
    l'absorber.
    """
    if coti_id:
        return COTI_TO_ORGANISME.get(coti_id, ORGANISME_INCONNU)

    upper = (libelle or "").upper()
    for marqueur, organisme in _LIBELLE_FALLBACK:
        if marqueur in upper:
            return organisme
    return ORGANISME_INCONNU


def default_accounts_for(organisme: str) -> Optional[AccountPair]:
    """Comptes par défaut d'un organisme, ou None s'il n'est pas rattaché."""
    return DEFAULT_ACCOUNTS.get(organisme)
