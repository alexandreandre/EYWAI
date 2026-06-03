"""Consensus scraper/Sonar limité aux cotisations ciblées (EYWAI_SYNC_COTISATION_IDS)."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Set

from cotisation_sync import parse_sync_cotisation_ids


def sync_target_item_ids() -> Optional[Set[str]]:
    """Ids de lignes à comparer pour valider le job ; None = bundle complet."""
    return parse_sync_cotisation_ids()


def signature_has_bundle_items(sig: dict, item_ids: Set[str]) -> bool:
    """True si la signature est un dict par cotisation_id (ex. AGIRC-ARRCO)."""
    return any(k in sig for k in item_ids)


def wrap_signatures_equal_for_targets(
    signatures_equal: Callable[[Any, Any], bool],
    item_ids: Optional[Set[str]],
) -> Callable[[Any, Any], bool]:
    if not item_ids:
        return signatures_equal

    def wrapped(a: Any, b: Any) -> bool:
        if isinstance(a, dict) and isinstance(b, dict):
            if signature_has_bundle_items(a, item_ids) or signature_has_bundle_items(
                b, item_ids
            ):
                subset_a = {k: a[k] for k in item_ids if k in a}
                subset_b = {k: b[k] for k in item_ids if k in b}
                return signatures_equal(subset_a, subset_b)
            # Cotisation simple (signature « valeurs ») : comparer la signature entière.
            return signatures_equal(a, b)
        return signatures_equal(a, b)

    return wrapped


def partial_targets_diverge(
    sig_a: dict,
    sig_b: dict,
    item_ids: Set[str],
    *,
    signatures_equal: Callable[[Any, Any], bool],
) -> list[str]:
    """Ids ciblés en échec de concordance (liste vide = accord sur le périmètre)."""
    if signature_has_bundle_items(sig_a, item_ids) or signature_has_bundle_items(
        sig_b, item_ids
    ):
        item_equal = make_bundle_item_equal(signatures_equal)
        return find_divergent_dict_keys(
            sig_a, sig_b, sorted(item_ids), item_equal=item_equal
        )
    if signatures_equal(sig_a, sig_b):
        return []
    return sorted(item_ids)


def make_bundle_item_equal(
    signatures_equal: Callable[[Any, Any], bool],
) -> Callable[[Any, Any], bool]:
    """Compare deux items d'un bundle via signatures_equal sur une clé id."""

    def item_equal(a: Any, b: Any) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return signatures_equal(a, b)
        cid = a.get("id") or b.get("id")
        if not cid:
            return False
        return signatures_equal({cid: a}, {cid: b})

    return item_equal


def find_divergent_dict_keys(
    sig_a: dict,
    sig_b: dict,
    keys: Iterable[str],
    *,
    item_equal: Callable[[Any, Any], bool],
) -> list[str]:
    """Retourne les clés où les deux signatures diffèrent (ordre stable)."""
    divergent: list[str] = []
    for key in keys:
        if key not in sig_a or key not in sig_b:
            divergent.append(key)
            continue
        if not item_equal(sig_a[key], sig_b[key]):
            divergent.append(key)
    return divergent


def format_target_divergence_reason(divergent_ids: list[str]) -> str:
    if not divergent_ids:
        return "Scraper et Sonar divergent — pas d'écriture automatique."
    labels = ", ".join(divergent_ids)
    return (
        f"Scraper et Sonar divergent sur le périmètre demandé ({labels}) "
        f"— pas d'écriture automatique."
    )


def format_out_of_scope_divergence_warning(divergent_ids: list[str]) -> str:
    labels = ", ".join(divergent_ids)
    return (
        f"Autres lignes du même scraper non concordantes (hors périmètre) : {labels}. "
        f"Contrôle complet recommandé."
    )
