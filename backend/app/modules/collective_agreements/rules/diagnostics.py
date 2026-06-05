"""Logs de diagnostic pour l'extraction des règles CC paie.

Filtrer dans les logs serveur : ``cc-extraction``
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.modules.collective_agreements.rules.schema import CCRulesDocument

logger = logging.getLogger(__name__)

LOG_TAG = "cc-extraction"


def payroll_grid_available(stats: dict[str, Any]) -> bool:
    """Aligné sur le frontend ``hasPayrollGridFromRules``."""
    if stats.get("salaires_minima_count", 0) > 0:
        return True
    return stats.get("grilles_with_minima_count", 0) > 0


def payroll_grid_available_from_rules(rules: dict[str, Any] | None) -> bool:
    """Vérifie si les règles persistées permettent d'afficher la grille paie."""
    if not rules or not isinstance(rules, dict):
        return False
    legacy = rules.get("salaires_minima") or []
    if isinstance(legacy, list) and legacy:
        return True
    grilles = rules.get("grilles_salaires") or []
    if not isinstance(grilles, list):
        return False
    return any(
        isinstance(g, dict)
        and isinstance(g.get("minima"), list)
        and g["minima"]
        for g in grilles
    )


def rules_doc_stats(doc: CCRulesDocument | None) -> dict[str, Any]:
    if doc is None:
        return {"doc": None}

    grilles = doc.grilles_salaires or []
    grilles_detail = [
        {
            "zone": g.zone_libelle or g.zone_type,
            "minima_count": len(g.minima),
            "sample_coefficients": [m.coefficient for m in g.minima[:5]],
            "sample_valeurs": [m.valeur for m in g.minima[:5]],
        }
        for g in grilles
    ]
    empty_grilles = sum(1 for g in grilles if not g.minima)

    prime = doc.prime_anciennete
    base = prime.base_de_calcul if prime else None

    stats: dict[str, Any] = {
        "grilles_count": len(grilles),
        "grilles_with_minima_count": sum(1 for g in grilles if g.minima),
        "empty_grilles_count": empty_grilles,
        "salaires_minima_count": len(doc.salaires_minima or []),
        "prime_bareme_count": len(prime.bareme) if prime and prime.bareme else 0,
        "prime_base_methode": base.methode if base else None,
        "prime_base_valeur": base.valeur if base else None,
        "grilles_detail": grilles_detail,
        "payroll_grid_available": False,
    }

    if doc.completude:
        stats["completude_niveau"] = doc.completude.niveau
        stats["completude_avertissements"] = list(doc.completude.avertissements or [])

    stats["payroll_grid_available"] = payroll_grid_available(stats)
    return stats


def partial_raw_stats(raw: dict[str, Any]) -> dict[str, Any]:
    grilles = raw.get("grilles_salaires") or []
    if not isinstance(grilles, list):
        grilles = []
    minima_counts = []
    for g in grilles:
        if isinstance(g, dict):
            m = g.get("minima") or []
            minima_counts.append(len(m) if isinstance(m, list) else 0)
    salaires = raw.get("salaires_minima") or []
    prime = raw.get("prime_anciennete") if isinstance(raw.get("prime_anciennete"), dict) else {}
    bareme = prime.get("bareme") if isinstance(prime, dict) else []
    return {
        "grilles_count": len(grilles),
        "grilles_minima_counts": minima_counts,
        "salaires_minima_count": len(salaires) if isinstance(salaires, list) else 0,
        "prime_bareme_count": len(bareme) if isinstance(bareme, list) else 0,
        "confidence": raw.get("confidence"),
    }


def log_cc_stage(idcc: str, stage: str, **fields: Any) -> None:
    logger.info("[%s] IDCC %s — %s — %s", LOG_TAG, idcc, stage, fields)


def log_cc_doc(idcc: str, stage: str, doc: CCRulesDocument | None) -> None:
    log_cc_stage(idcc, stage, **rules_doc_stats(doc))


def log_cc_partial(idcc: str, chunk_idx: int, chunk_total: int, raw: dict[str, Any]) -> None:
    log_cc_stage(
        idcc,
        f"chunk_ia_{chunk_idx + 1}/{chunk_total}",
        **partial_raw_stats(raw),
    )


def log_cc_outcome(
    idcc: str,
    *,
    success: bool,
    agreement_id: Optional[str] = None,
    error: Optional[str] = None,
    tokens_used: int = 0,
    rules_skipped: bool = False,
    doc: CCRulesDocument | None = None,
    persisted_rules: Optional[dict[str, Any]] = None,
) -> None:
    payload: dict[str, Any] = {
        "success": success,
        "agreement_id": agreement_id,
        "error": error,
        "tokens_used": tokens_used,
        "rules_skipped": rules_skipped,
    }
    if doc is not None:
        payload.update(rules_doc_stats(doc))
    if persisted_rules is not None:
        grilles = persisted_rules.get("grilles_salaires") or []
        legacy = persisted_rules.get("salaires_minima") or []
        persisted_stats = {
            "persisted_grilles_count": len(grilles) if isinstance(grilles, list) else 0,
            "persisted_salaires_minima_count": len(legacy) if isinstance(legacy, list) else 0,
            "persisted_grilles_with_minima": sum(
                1
                for g in grilles
                if isinstance(g, dict) and isinstance(g.get("minima"), list) and g["minima"]
            )
            if isinstance(grilles, list)
            else 0,
        }
        persisted_stats["persisted_payroll_grid_available"] = (
            persisted_stats["persisted_salaires_minima_count"] > 0
            or persisted_stats["persisted_grilles_with_minima"] > 0
        )
        payload.update(persisted_stats)

    level = logging.INFO if success else logging.WARNING
    logger.log(level, "[%s] IDCC %s — outcome — %s", LOG_TAG, idcc, payload)
