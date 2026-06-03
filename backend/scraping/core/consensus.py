"""Concordance entre sources de scraping."""

from __future__ import annotations

from typing import Any, Callable, List, Tuple

from utils import consensus_satisfied as _consensus_satisfied
from utils import prefer_primary_on_divergence as _prefer_primary


def consensus_satisfied(
    sigs: List[Any],
    pair_equal: Callable[[Any, Any], bool],
) -> Tuple[bool, int]:
    return _consensus_satisfied(sigs, pair_equal)


def prefer_primary_on_divergence(
    ok: bool,
    ref_idx: int,
    labels: List[str],
    sigs: List[Any],
    primary_label: str,
    sig_valid: Callable[[Any], bool],
) -> Tuple[bool, int]:
    return _prefer_primary(ok, ref_idx, labels, sigs, primary_label, sig_valid)


def merge_source_links(payloads: list[dict]) -> list[str]:
    seen: set[str] = set()
    links: list[str] = []
    for p in payloads:
        for s in p.get("meta", {}).get("source", []):
            if not isinstance(s, dict):
                continue
            url = s.get("url")
            if url and isinstance(url, str):
                url = url.strip()
                if url and url not in seen:
                    seen.add(url)
                    links.append(url)
    return links
