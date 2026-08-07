"""
Correspondance entre clés payroll_config (rate_key), lignes de cotisation et sources scraping.

Aligné sur CONFIG_KEY_TO_UPDATE / ITEM_ID_TO_PATCH des orchestrateurs.
"""

from __future__ import annotations

# rate_key (payroll_config.config_key) -> source_key scraping (table scraping_sources)
RATE_KEY_TO_SOURCE_KEYS: dict[str, list[str]] = {
    "smic": ["SMIC"],
    "pss": ["PSS"],
    "ij_plafonds": ["IJ_MALADIE"],
    "pas": ["PAS"],
    "frais_pro": ["FRAIS_PRO"],
    "avantages_en_nature": ["AVANTAGES"],
    "heures_supp": ["HEURES_SUPP"],
    "primes": ["PRIMES"],
    "baremes_km": ["BAREME_INDEMNITE_KILOMETRIQUE"],
    "taux_vmrr": ["VM"],
    "alternance": ["ALTERNANCE"],
    "cotisations": [
        "AGIRC-ARRCO",
        "AGS",
        "CSG",
        "CSA",
        "FNAL",
        "ALLOCATIONS_FAMILIALES",
        "ASSURANCE_CHOMAGE",
        "DIALOGUE_SOCIAL",
        "MMID_PATRONAL",
        "MMID_SALARIAL",
        "VIEILLESSE_PATRONAL",
        "VIEILLESSE_SALARIAL",
        "CFP",
        "TAXE_APPRENTISSAGE",
        "PREVOYANCE_CADRE",
        "PREVOYANCE_NON_CADRE",
    ],
    "taux_interet_legal": ["TAUX_INTERET_LEGAL"],
    "cdd": ["CDD"],
    "interim": ["INTERIM"],
    "stage": ["STAGE"],
    "maladie": ["MALADIE"],
    "jei": ["JEI"],
    "oeth": ["OETH"],
    "reduction_generale": ["REDUCTION_GENERALE"],
    "mandataire": ["MANDATAIRE"],
    "comptes_avances_acomptes": ["COMPTES_AVANCES_ACOMPTES"],
}

# cotisation.id dans config_data.cotisations -> source(s) scraping
COTISATION_ID_TO_SOURCE_KEYS: dict[str, list[str]] = {
    "retraite_comp_t1": ["AGIRC-ARRCO"],
    "retraite_comp_t2": ["AGIRC-ARRCO"],
    "ceg_t1": ["AGIRC-ARRCO"],
    "ceg_t2": ["AGIRC-ARRCO"],
    "cet": ["AGIRC-ARRCO"],
    "apec": ["AGIRC-ARRCO"],
    "ags": ["AGS"],
    "allocations_familiales": ["ALLOCATIONS_FAMILIALES"],
    "csg": ["CSG"],
    "csa": ["CSA"],
    "fnal": ["FNAL"],
    "assurance_chomage": ["ASSURANCE_CHOMAGE"],
    "dialogue_social": ["DIALOGUE_SOCIAL"],
    "securite_sociale_maladie": ["MMID_PATRONAL", "MMID_SALARIAL"],
    "CFP": ["CFP"],
    "cfp": ["CFP"],
    "taxe_apprentissage": ["TAXE_APPRENTISSAGE"],
    "taxe_apprentissage_solde": ["TAXE_APPRENTISSAGE"],
    "retraite_secu_plafond": ["VIEILLESSE_PATRONAL", "VIEILLESSE_SALARIAL"],
    "retraite_secu_deplafond": ["VIEILLESSE_PATRONAL", "VIEILLESSE_SALARIAL"],
    "vieillesse_patronal": ["VIEILLESSE_PATRONAL"],
    "vieillesse_salarial": ["VIEILLESSE_SALARIAL"],
    "prevoyance_cadre": ["PREVOYANCE_CADRE"],
    "prevoyance_non_cadre": ["PREVOYANCE_NON_CADRE"],
}


def normalize_source_key(key: str) -> str:
    return key.strip().upper().replace("-", "_")


def resolve_source_keys(
    *,
    rate_keys: list[str] | None = None,
    source_keys: list[str] | None = None,
    cotisation_ids: list[str] | None = None,
) -> list[str]:
    """Résout la liste dédupliquée de source_key à exécuter (vide = sync globale)."""
    if not cotisation_ids and not source_keys and not rate_keys:
        return []

    resolved: list[str] = []
    seen: set[str] = set()

    def add(key: str) -> None:
        norm = normalize_source_key(key)
        if norm not in seen:
            seen.add(norm)
            resolved.append(key)

    if cotisation_ids:
        for cid in cotisation_ids:
            keys = COTISATION_ID_TO_SOURCE_KEYS.get(cid)
            if keys is None:
                keys = COTISATION_ID_TO_SOURCE_KEYS.get(cid.strip().upper())
            if keys is None and cid:
                keys = COTISATION_ID_TO_SOURCE_KEYS.get(cid.strip().lower())
            for sk in keys or []:
                add(sk)
    if source_keys:
        for sk in source_keys:
            add(sk)
    if rate_keys:
        for rk in rate_keys:
            for sk in RATE_KEY_TO_SOURCE_KEYS.get(rk, []):
                add(sk)

    return resolved


def all_known_rate_keys() -> list[str]:
    return list(RATE_KEY_TO_SOURCE_KEYS.keys())


def all_page_source_keys() -> list[str]:
    """Clés scraping couvrant toute la page Suivi des taux (mise à jour complète)."""
    seen: set[str] = set()
    resolved: list[str] = []
    for source_keys in RATE_KEY_TO_SOURCE_KEYS.values():
        for source_key in source_keys:
            norm = normalize_source_key(source_key)
            if norm in seen:
                continue
            seen.add(norm)
            resolved.append(source_key)
    return resolved
