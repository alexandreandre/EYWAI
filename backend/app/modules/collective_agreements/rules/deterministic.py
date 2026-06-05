"""Couche déterministe : parser KALI + seed officiel avant persistance."""

from __future__ import annotations

from app.modules.collective_agreements.rules.bareme_parser import parse_smh_national
from app.modules.collective_agreements.rules.completude import finalize_document
from app.modules.collective_agreements.rules.diagnostics import log_cc_stage
from app.modules.collective_agreements.rules.schema import CCRulesDocument
from app.modules.collective_agreements.rules.seeds import apply_seed_to_document, get_seed


def _has_payroll_minima(doc: CCRulesDocument) -> bool:
    return bool(doc.salaires_minima) or any(g.minima for g in doc.grilles_salaires)


def apply_deterministic_layer(
    doc: CCRulesDocument,
    full_text: str,
    *,
    idcc: str,
) -> CCRulesDocument:
    """
    Complète le document avec parser SMH et/ou seed officiel si la grille IA est vide.
    """
    seed = get_seed(idcc)

    if not _has_payroll_minima(doc):
        parsed_grille = parse_smh_national(full_text)
        if parsed_grille:
            log_cc_stage(
                idcc,
                "deterministic_smh_parser",
                minima_count=len(parsed_grille.minima),
                date_effet=parsed_grille.date_effet,
            )
            doc.grilles_salaires = [parsed_grille]
        elif seed and seed.grille:
            log_cc_stage(
                idcc,
                "deterministic_smh_seed",
                minima_count=len(seed.grille.minima),
                source="seed_officiel",
            )
            doc.grilles_salaires = [seed.grille]

    if seed:
        doc = apply_seed_to_document(doc, seed)

    return finalize_document(doc)
