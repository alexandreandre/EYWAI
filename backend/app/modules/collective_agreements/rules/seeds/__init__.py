"""Seeds officiels de règles paie par IDCC (filet de sécurité déterministe)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    CpAnciennete,
    GrilleSalaires,
    PrimeAnciennete,
)


@dataclass
class CCRulesSeed:
    """Fragment de règles paie à injecter si l'extraction IA est incomplète."""

    grille: Optional[GrilleSalaires] = None
    prime: Optional[PrimeAnciennete] = None
    cp_anciennete: Optional[CpAnciennete] = None


def _normalize_idcc(idcc: str) -> str:
    s = (idcc or "").strip()
    if s.isdigit():
        return s.zfill(4) if len(s) <= 4 else s
    return s


def get_seed(idcc: str) -> Optional[CCRulesSeed]:
    """Retourne le seed officiel pour un IDCC, ou None."""
    norm = _normalize_idcc(idcc)
    stripped = norm.lstrip("0") or "0"
    if norm == "3248" or stripped == "3248":
        from app.modules.collective_agreements.rules.seeds.metallurgie_3248 import (
            METALLURGIE_3248_SEED,
        )

        return METALLURGIE_3248_SEED
    # Plasturgie : IDCC officiel 0292 ; alias 1297 utilisé dans certains jeux de données
    if norm in ("0292", "1297") or stripped in ("292", "1297"):
        from app.modules.collective_agreements.rules.seeds.plasturgie_0292 import (
            PLASTURGIE_0292_SEED,
        )

        return PLASTURGIE_0292_SEED
    return None


def apply_seed_to_document(doc: CCRulesDocument, seed: CCRulesSeed) -> CCRulesDocument:
    """Fusionne le seed dans un document sans écraser les données IA existantes."""
    has_minima = bool(doc.salaires_minima) or any(g.minima for g in doc.grilles_salaires)
    if seed.grille and not has_minima:
        doc.grilles_salaires = [seed.grille]

    if seed.prime:
        if not doc.prime_anciennete:
            doc.prime_anciennete = seed.prime
        else:
            prime = doc.prime_anciennete
            if seed.prime.taux_par_classe and not prime.taux_par_classe:
                prime.taux_par_classe = seed.prime.taux_par_classe
            if seed.prime.base_de_calcul and not prime.base_de_calcul:
                prime.base_de_calcul = seed.prime.base_de_calcul
            if seed.prime.bareme and not prime.bareme:
                prime.bareme = seed.prime.bareme

    if seed.cp_anciennete and not doc.cp_anciennete:
        doc.cp_anciennete = seed.cp_anciennete

    return doc
