"""Normalisation, comparaison et build pour AGIRC-ARRCO."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, Optional

from core.cotisation_helpers import patch_cotisation_fields
from core.validation import ValidationResult

logger = logging.getLogger(__name__)

ITEMS_ID_TO_PATCH = [
    "retraite_comp_t1",
    "retraite_comp_t2",
    "ceg_t1",
    "ceg_t2",
    "cet",
    "apec",
]

BASE_MAPPING = {
    "retraite_comp_t1": "brut_plafonne",
    "retraite_comp_t2": "tranche_2",
    "ceg_t1": "brut_plafonne",
    "ceg_t2": "tranche_2",
    "cet": "assiette_cet",
    "apec": "brut_cadre_4_plafonds",
}

DEFAULT_NEW_ITEMS = {
    "retraite_comp_t1": {
        "id": "retraite_comp_t1",
        "libelle": "Retraite complémentaire Tranche 1",
        "base": "brut_plafonne",
    },
    "retraite_comp_t2": {
        "id": "retraite_comp_t2",
        "libelle": "Retraite complémentaire Tranche 2",
        "base": "tranche_2",
    },
    "ceg_t1": {
        "id": "ceg_t1",
        "libelle": "CEG Tranche 1",
        "base": "brut_plafonne",
    },
    "ceg_t2": {
        "id": "ceg_t2",
        "libelle": "CEG Tranche 2",
        "base": "tranche_2",
    },
    "cet": {
        "id": "cet",
        "libelle": "CET",
        "base": "assiette_cet",
    },
    "apec": {
        "id": "apec",
        "libelle": "APEC",
        "base": "brut_cadre_4_plafonds",
    },
}


def compare_floats(a: float | None, b: float | None, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return math.isclose(float(a), float(b), abs_tol=tol)
    except (ValueError, TypeError):
        return False


def enrich_payload_sources(payload: Dict[str, Any]) -> None:
    """Remonte les sources bundle + items dans meta.source pour merge_source_links."""
    seen: set[str] = set()
    merged: list[dict] = []

    def add_from(meta_list: list | None) -> None:
        for s in meta_list or []:
            if not isinstance(s, dict):
                continue
            url = s.get("url")
            if url and isinstance(url, str):
                url = url.strip()
                if url and url not in seen:
                    seen.add(url)
                    merged.append(s)

    add_from(payload.get("meta", {}).get("source"))
    for it in payload.get("items", []):
        add_from(it.get("meta", {}).get("source"))
    if merged:
        payload.setdefault("meta", {})["source"] = merged


def accept_payload(_label: str, payload: Dict[str, Any]) -> bool:
    enrich_payload_sources(payload)
    return True


def core_signature(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if (
        payload.get("id") != "agirc_arrco_bundle"
        or payload.get("type") != "cotisation_bundle"
    ):
        raise ValueError("Payload inattendu: bundle AGIRC-ARRCO requis.")

    items = payload.get("items", [])
    out: Dict[str, Dict[str, Any]] = {}

    for it in items:
        _id = it.get("id")
        if not _id:
            continue

        sal = it.get("valeurs", {}).get("salarial", None)
        pat = it.get("valeurs", {}).get("patronal", None)

        try:
            sal_norm = None if sal is None else round(float(sal), 6)
            pat_norm = None if pat is None else round(float(pat), 6)
        except (ValueError, TypeError):
            logger.warning(
                "Valeur non numérique pour '%s' depuis %s.",
                _id,
                payload.get("__script"),
            )
            sal_norm, pat_norm = None, None

        correct_base = BASE_MAPPING.get(_id) or it.get("base")

        out[_id] = {
            "id": _id,
            "type": "cotisation",
            "libelle": it.get("libelle"),
            "base": correct_base,
            "valeurs": {"salarial": sal_norm, "patronal": pat_norm},
        }

    missing = [cid for cid in ITEMS_ID_TO_PATCH if cid not in out]
    if missing:
        raise ValueError(f"Items manquants dans le bundle: {missing}")

    return out


def equal_item(a: Dict[str, Any], b: Dict[str, Any], tol: float = 1e-9) -> bool:
    for k in ("id", "type", "libelle", "base"):
        if a.get(k) != b.get(k):
            return False
    sa, pa = a["valeurs"]["salarial"], a["valeurs"]["patronal"]
    sb, pb = b["valeurs"]["salarial"], b["valeurs"]["patronal"]
    return compare_floats(sa, sb, tol) and compare_floats(pa, pb, tol)


def bundles_pair_equal(
    ba: Dict[str, Dict[str, Any]],
    bb: Dict[str, Dict[str, Any]],
    item_ids: Optional[Iterable[str]] = None,
) -> bool:
    if item_ids is not None:
        ids = list(item_ids)
    elif ba.keys() == bb.keys() and ba:
        # Sous-ensemble (consensus partiel sur une ou plusieurs lignes du bundle).
        ids = sorted(ba.keys())
    else:
        ids = ITEMS_ID_TO_PATCH
    for cid in ids:
        ia, ib = ba.get(cid), bb.get(cid)
        if ia is None or ib is None:
            return False
        if not equal_item(ia, ib):
            return False
    return True


def validate_signature(sig: Dict[str, Dict[str, Any]]) -> ValidationResult:
    for cid in ITEMS_ID_TO_PATCH:
        item = sig.get(cid)
        if not item:
            return ValidationResult(False, f"Item manquant: {cid}")
        sal = item["valeurs"].get("salarial")
        pat = item["valeurs"].get("patronal")
        if sal is None and pat is None:
            return ValidationResult(False, f"Taux manquants pour {cid}")
    return ValidationResult(True)


def build_config_data(
    sig: Dict[str, Dict[str, Any]], current: Optional[dict]
) -> Dict[str, Any]:
    cur = current["config_data"] if current else None
    patches = [
        (
            item_id,
            {
                "libelle": item["libelle"],
                "base": item["base"],
                "salarial": item["valeurs"]["salarial"],
                "patronal": item["valeurs"]["patronal"],
            },
        )
        for item_id, item in sig.items()
        if item_id in ITEMS_ID_TO_PATCH
    ]
    return patch_cotisation_fields(
        cur,
        patches=patches,
        default_new_items=DEFAULT_NEW_ITEMS,
    )
