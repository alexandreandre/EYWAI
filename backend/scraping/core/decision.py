"""Classification de la décision multi-sources (cas A / B / C).

Fonction pure et testable : elle n'écrit rien, ne lit aucune ressource externe.
Elle décrit *ce qui s'est passé* entre les sources ; c'est l'orchestrateur qui
décide ensuite, en fonction du tier, d'écrire ou de passer par la validation humaine.

Cas (selon l'architecture v2) :
- A : accord (2 déterministes, ou scraper + Sonar au même niveau si dual_source_consensus).
- B : une source déterministe valide sans paire Sonar requise (mode legacy).
- C : désaccord ou sources insuffisantes — pas d'écriture si dual_source_consensus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from utils import is_ai_scraper_label


@dataclass
class DecisionResult:
    """Résultat de la classification multi-sources."""

    case: str  # "A" | "B" | "C"
    ok: bool  # une signature finale exploitable existe
    ref_idx: int  # index (dans les listes d'entrée) de la signature retenue
    sources_agreement: bool  # les sources déterministes concordent
    ai_divergence: bool  # l'IA est présente et diverge de la signature retenue
    deterministic_count: int
    ai_count: int
    discrepancies: List[dict] = field(default_factory=list)
    reason: str = ""


def _equal_safe(
    signatures_equal: Callable[[Any, Any], bool],
    a: Any,
    b: Any,
) -> bool:
    try:
        return bool(signatures_equal(a, b))
    except Exception:
        return False


def _find_agreeing_pair(
    indices: List[int],
    sigs: List[Any],
    signatures_equal: Callable[[Any, Any], bool],
) -> Optional[tuple[int, int]]:
    for a in range(len(indices)):
        for b in range(a + 1, len(indices)):
            i, j = indices[a], indices[b]
            if _equal_safe(signatures_equal, sigs[i], sigs[j]):
                return (i, j)
    return None


def _classify_scraper_sonar_pair(
    labels: List[str],
    sigs: List[Any],
    *,
    primary_label: Optional[str],
    signatures_equal: Callable[[Any, Any], bool],
    discrepancies: List[dict],
    partial_failure_reason: Optional[str] = None,
) -> DecisionResult:
    """Scraper (primary) + Sonar : même niveau — LegiSocial ignoré si encore présent."""
    det_indices = [i for i, lab in enumerate(labels) if not is_ai_scraper_label(lab)]
    ai_indices = [i for i, lab in enumerate(labels) if is_ai_scraper_label(lab)]

    if not primary_label:
        return DecisionResult(
            case="C",
            ok=False,
            ref_idx=0,
            sources_agreement=False,
            ai_divergence=False,
            deterministic_count=len(det_indices),
            ai_count=len(ai_indices),
            discrepancies=discrepancies,
            reason="Consensus dual : primary_label manquant sur la spec.",
        )

    primary_matches = [i for i in det_indices if labels[i] == primary_label]
    if len(primary_matches) != 1:
        return DecisionResult(
            case="C",
            ok=False,
            ref_idx=det_indices[0] if det_indices else 0,
            sources_agreement=False,
            ai_divergence=False,
            deterministic_count=len(det_indices),
            ai_count=len(ai_indices),
            discrepancies=discrepancies,
            reason="Consensus dual : source primary absente ou en échec.",
        )
    if len(ai_indices) != 1:
        return DecisionResult(
            case="C",
            ok=False,
            ref_idx=primary_matches[0],
            sources_agreement=False,
            ai_divergence=False,
            deterministic_count=len(det_indices),
            ai_count=len(ai_indices),
            discrepancies=discrepancies,
            reason="Consensus dual : Sonar requis et absent ou en échec.",
        )

    det_idx = primary_matches[0]
    ai_idx = ai_indices[0]
    if _equal_safe(signatures_equal, sigs[det_idx], sigs[ai_idx]):
        return DecisionResult(
            case="A",
            ok=True,
            ref_idx=det_idx,
            sources_agreement=True,
            ai_divergence=False,
            deterministic_count=1,
            ai_count=1,
            discrepancies=discrepancies,
            reason="Scraper et Sonar concordent (même niveau).",
        )

    return DecisionResult(
        case="C",
        ok=False,
        ref_idx=det_idx,
        sources_agreement=False,
        ai_divergence=True,
        deterministic_count=1,
        ai_count=1,
        discrepancies=discrepancies,
        reason=partial_failure_reason
        or "Scraper et Sonar divergent — pas d'écriture automatique.",
    )


def classify_decision(
    labels: List[str],
    sigs: List[Any],
    *,
    primary_label: Optional[str] = None,
    signatures_equal: Callable[[Any, Any], bool],
    sig_valid: Callable[[Any], bool] = lambda s: s is not None,
    dual_source_consensus: bool = False,
    partial_failure_reason: Optional[str] = None,
) -> DecisionResult:
    """Classe la décision à partir des signatures métier valides.

    `labels` et `sigs` sont alignés (même longueur) et ne contiennent que les
    sources ayant produit une signature métier valide.
    """
    det_indices = [i for i, lab in enumerate(labels) if not is_ai_scraper_label(lab)]
    ai_indices = [i for i, lab in enumerate(labels) if is_ai_scraper_label(lab)]

    discrepancies = [
        {
            "label": labels[i],
            "is_ai": is_ai_scraper_label(labels[i]),
            "signature": sigs[i],
        }
        for i in range(len(labels))
    ]

    if dual_source_consensus:
        return _classify_scraper_sonar_pair(
            labels,
            sigs,
            primary_label=primary_label,
            signatures_equal=signatures_equal,
            discrepancies=discrepancies,
            partial_failure_reason=partial_failure_reason,
        )

    def _ai_diverges(ref: int) -> bool:
        return any(
            not _equal_safe(signatures_equal, sigs[ai], sigs[ref]) for ai in ai_indices
        )

    def _primary_index_within(indices: List[int]) -> Optional[int]:
        if not primary_label:
            return None
        for i in indices:
            if labels[i] == primary_label:
                return i
        return None

    # --- Cas A / C : au moins deux sources déterministes valides ---
    if len(det_indices) >= 2:
        pair = _find_agreeing_pair(det_indices, sigs, signatures_equal)
        if pair is not None:
            i, j = pair
            primary_in_pair = _primary_index_within([i, j])
            ref = primary_in_pair if primary_in_pair is not None else min(i, j)
            return DecisionResult(
                case="A",
                ok=True,
                ref_idx=ref,
                sources_agreement=True,
                ai_divergence=_ai_diverges(ref),
                deterministic_count=len(det_indices),
                ai_count=len(ai_indices),
                discrepancies=discrepancies,
                reason="Les sources déterministes concordent (IA témoin).",
            )
        # Désaccord déterministe : tentative de repli sur la source primaire.
        primary_det = _primary_index_within(det_indices)
        if primary_det is not None and sig_valid(sigs[primary_det]):
            return DecisionResult(
                case="C",
                ok=True,
                ref_idx=primary_det,
                sources_agreement=False,
                ai_divergence=_ai_diverges(primary_det),
                deterministic_count=len(det_indices),
                ai_count=len(ai_indices),
                discrepancies=discrepancies,
                reason="Désaccord déterministe non résolu — repli sur la source primaire.",
            )
        return DecisionResult(
            case="C",
            ok=False,
            ref_idx=det_indices[0],
            sources_agreement=False,
            ai_divergence=False,
            deterministic_count=len(det_indices),
            ai_count=len(ai_indices),
            discrepancies=discrepancies,
            reason="Désaccord déterministe non résolu, aucune référence primaire.",
        )

    # --- Cas B : une seule source déterministe valide ---
    if len(det_indices) == 1:
        ref = det_indices[0]
        return DecisionResult(
            case="B",
            ok=sig_valid(sigs[ref]),
            ref_idx=ref,
            sources_agreement=False,
            ai_divergence=_ai_diverges(ref),
            deterministic_count=1,
            ai_count=len(ai_indices),
            discrepancies=discrepancies,
            reason="Une seule source déterministe valide (l'autre a cassé).",
        )

    # --- Cas B (dégradé) : aucune source déterministe, IA seule ---
    if ai_indices:
        ref = ai_indices[0]
        return DecisionResult(
            case="B",
            ok=sig_valid(sigs[ref]),
            ref_idx=ref,
            sources_agreement=False,
            ai_divergence=False,
            deterministic_count=0,
            ai_count=len(ai_indices),
            discrepancies=discrepancies,
            reason="Aucune source déterministe valide — IA seule (candidate).",
        )

    return DecisionResult(
        case="C",
        ok=False,
        ref_idx=0,
        sources_agreement=False,
        ai_divergence=False,
        deterministic_count=0,
        ai_count=0,
        discrepancies=discrepancies,
        reason="Aucune signature valide.",
    )
