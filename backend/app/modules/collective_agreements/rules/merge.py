"""Fusion de résultats d'extraction multi-chunks."""

from __future__ import annotations

from typing import Any

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    PalierAnciennete,
    PrimeAnciennete,
    SalaireMinimum,
    parse_extraction_result,
)


def merge_extraction_results(
    results: list[dict[str, Any]],
    *,
    idcc: str,
) -> CCRulesDocument:
    """Fusionne plusieurs extractions partielles en un document unique."""
    if not results:
        return CCRulesDocument(idcc=idcc)

    if len(results) == 1:
        doc = parse_extraction_result(results[0])
        doc.idcc = idcc
        if doc.salaires_minima:
            by_coeff: dict[float, SalaireMinimum] = {}
            for m in doc.salaires_minima:
                by_coeff[m.coefficient] = m
            doc.salaires_minima = list(by_coeff.values())
        return doc

    all_baremes: list[PalierAnciennete] = []
    best_base: dict[str, Any] | None = None
    minima_by_coeff: dict[float, SalaireMinimum] = {}
    all_citations: list[dict[str, str]] = []
    confidence_rank = {"low": 0, "medium": 1, "high": 2}
    best_confidence = "low"

    for raw in results:
        doc = parse_extraction_result(raw)
        if doc.prime_anciennete:
            all_baremes.extend(doc.prime_anciennete.bareme)
            if doc.prime_anciennete.base_de_calcul and not best_base:
                best_base = doc.prime_anciennete.base_de_calcul.model_dump()
        for m in doc.salaires_minima:
            minima_by_coeff[m.coefficient] = m
        if doc.meta:
            all_citations.extend([c.model_dump() for c in doc.meta.citations])
            conf = doc.meta.confidence
            if confidence_rank.get(conf, 0) > confidence_rank.get(best_confidence, 0):
                best_confidence = conf

    merged_bareme = _dedupe_bareme(all_baremes)
    prime = None
    if merged_bareme or best_base:
        from app.modules.collective_agreements.rules.schema import BaseCalculPrime

        base_obj = BaseCalculPrime(**best_base) if best_base else None
        prime = PrimeAnciennete(bareme=merged_bareme, base_de_calcul=base_obj)

    merged = parse_extraction_result(
        {
            "idcc": idcc,
            "prime_anciennete": (
                {
                    "bareme": [{"annees_min": p.annees_min, "taux": p.taux} for p in merged_bareme],
                    "base_de_calcul": best_base,
                }
                if prime
                else None
            ),
            "salaires_minima": [
                {
                    "coefficient": m.coefficient,
                    "valeur": m.valeur,
                    "libelle": m.libelle,
                }
                for m in minima_by_coeff.values()
            ],
            "confidence": best_confidence,
            "citations": all_citations,
        }
    )
    merged.idcc = idcc
    return merged


def _dedupe_bareme(baremes: list[PalierAnciennete]) -> list[PalierAnciennete]:
    by_year: dict[float, PalierAnciennete] = {}
    for p in baremes:
        existing = by_year.get(p.annees_min)
        if existing is None or p.taux > existing.taux:
            by_year[p.annees_min] = p
    return sorted(by_year.values(), key=lambda x: x.annees_min)
