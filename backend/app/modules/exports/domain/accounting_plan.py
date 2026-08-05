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

# --- Familles d'éléments hors cotisations -----------------------------------
#
# Les éléments hors brut (primes non soumises, retenues) n'ont pas d'identifiant
# stable : `prime_id` est fabriqué depuis le libellé libre saisi par la RH, si
# bien qu'on trouve en base « indemnité_de_transport » et « indemnite_de_transport »
# pour la même chose, et un identifiant par salarié pour les prêts
# (« contrat_de_pret_<nom> »).
#
# Le rattachement passe donc par une famille : une clé stable, sans nom propre,
# vers laquelle on normalise le libellé. C'est cette famille qui porte les
# comptes, jamais le libellé.
#
# Une famille sans compte par défaut est volontaire : le compte dépend du plan
# du cabinet et sera paramétré par société. L'export refusera de sortir tant
# qu'il manque, plutôt que d'inventer une imputation.

FAMILLE_TRANSPORT = "indemnite_transport"
FAMILLE_PANIER = "panier"
FAMILLE_CANTINE = "cantine"
FAMILLE_PRET = "pret_employeur"
FAMILLE_AVANCE_PARTICIPATION = "avance_participation"
FAMILLE_NOTE_DE_FRAIS = "note_de_frais"
FAMILLE_IJSS = "ijss"
FAMILLE_PARTICIPATION = "participation"
FAMILLE_PARTICIPATION_PEE = "participation_pee"
FAMILLE_ACOMPTE_VERSE = "acompte_verse"
FAMILLE_INCONNUE = "INCONNUE"

# Préfixes normalisés (minuscules, sans accents) → famille.
# L'ordre compte : le premier préfixe qui correspond gagne.
_FAMILLE_PREFIXES = (
    ("avance participation", FAMILLE_AVANCE_PARTICIPATION),
    ("acompte sur participation", FAMILLE_AVANCE_PARTICIPATION),
    ("acompte participation", FAMILLE_AVANCE_PARTICIPATION),
    ("contrat de pret", FAMILLE_PRET),
    ("remboursement pret", FAMILLE_PRET),
    ("indemnite de transport", FAMILLE_TRANSPORT),
    ("remboursement transport", FAMILLE_TRANSPORT),
    ("indemnite de panier", FAMILLE_PANIER),
    ("paniers jours", FAMILLE_PANIER),
    ("paniers repas", FAMILLE_PANIER),
    ("panier", FAMILLE_PANIER),
    ("remise cantine", FAMILLE_CANTINE),
    ("cantine", FAMILLE_CANTINE),
    ("remboursement de notes de frais", FAMILLE_NOTE_DE_FRAIS),
    ("remboursement note de frais", FAMILLE_NOTE_DE_FRAIS),
    ("ijss", FAMILLE_IJSS),
    # Après les avances et acomptes de participation, qui sont autre chose.
    ("participation", FAMILLE_PARTICIPATION),
)

# Comptes par défaut des familles. Une famille absente doit être paramétrée par
# société avant que l'OD puisse sortir — on ne devine pas une imputation.
FAMILY_ACCOUNTS: Dict[str, AccountPair] = {
    FAMILLE_TRANSPORT: AccountPair(compte_charge="648000", compte_tiers=""),
    FAMILLE_PRET: AccountPair(compte_charge="", compte_tiers="274000"),
    FAMILLE_NOTE_DE_FRAIS: AccountPair(compte_charge="", compte_tiers="428625"),
    # La participation de l'exercice précédent a été provisionnée à sa clôture :
    # son versement éteint la dette 424, il ne crée pas de charge.
    FAMILLE_PARTICIPATION: AccountPair(compte_charge="", compte_tiers="424000"),
    # Compte provisoire pour la part placée sur un plan d'épargne : à confirmer
    # avec le cabinet, l'OD de référence n'en comporte aucune.
    FAMILLE_PARTICIPATION_PEE: AccountPair(compte_charge="", compte_tiers="424600"),
    FAMILLE_AVANCE_PARTICIPATION: AccountPair(compte_charge="", compte_tiers="425300"),
    FAMILLE_ACOMPTE_VERSE: AccountPair(compte_charge="", compte_tiers="425100"),
}


def _normalize_libelle(libelle: str) -> str:
    """Minuscules, sans accents, espaces réduits — pour comparer des libellés
    saisis à la main, qui varient en casse et en accentuation."""
    import unicodedata

    sans_accents = "".join(
        c
        for c in unicodedata.normalize("NFD", libelle or "")
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sans_accents.lower().replace("_", " ").split())


def resolve_element_family(libelle: str, prime_id: Optional[str] = None) -> str:
    """Rattache un élément hors brut à sa famille comptable.

    Le libellé et l'identifiant sont tous deux du texte libre : on les normalise
    et on cherche un préfixe connu. Retourne `INCONNUE` si rien ne correspond —
    l'appelant doit le signaler, pas choisir un compte au hasard.
    """
    for candidat in (libelle, prime_id or ""):
        normalise = _normalize_libelle(candidat)
        if not normalise:
            continue
        for prefixe, famille in _FAMILLE_PREFIXES:
            if normalise.startswith(prefixe):
                return famille
    return FAMILLE_INCONNUE


def default_accounts_for_family(famille: str) -> Optional[AccountPair]:
    """Comptes par défaut d'une famille, ou None si elle doit être paramétrée."""
    return FAMILY_ACCOUNTS.get(famille)


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
