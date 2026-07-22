# backend/scraping/core/ai_scalar_spec.py
"""Fabrique générique de RateSpec IA mono-source (scalaires, merge sûr)."""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.rate_spec import PersistenceMode, RateSpec, ScraperScript
from core.validation import ValidationResult, require_float_range, validate_all


def _payload_valeurs(payload: Dict[str, Any]) -> Dict[str, Any]:
    return payload.get("valeurs") or payload.get("sections") or {}


def make_signature(keys: List[str]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
        v = _payload_valeurs(payload)
        return {k: v.get(k) for k in keys}

    return core_signature


def make_signatures_equal(
    keys: List[str], tol: float = 1e-9
) -> Callable[[Dict[str, Any], Dict[str, Any]], bool]:
    def signatures_equal(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        for k in keys:
            va, vb = a.get(k), b.get(k)
            if va is None or vb is None:
                if va is not vb:
                    return False
                continue
            if not math.isclose(float(va), float(vb), abs_tol=tol):
                return False
        return True

    return signatures_equal


def make_range_validator(
    bounds: Dict[str, Tuple[float, float]]
) -> Callable[[Dict[str, Any]], ValidationResult]:
    def validate(sig: Dict[str, Any]) -> ValidationResult:
        return validate_all(
            [
                (lambda k=k, lo=lo, hi=hi: require_float_range(
                    sig.get(k), name=k, min_v=lo, max_v=hi
                ))
                for k, (lo, hi) in bounds.items()
            ]
        )

    return validate


def make_merge_builder(
    setters: Dict[str, List[str]], *, require_current: bool = True
) -> Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]:
    """Fusionne les valeurs vérifiées dans la config existante (jamais reconstruite)."""

    def build(sig: Dict[str, Any], current: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        cur = (current or {}).get("config_data") if current else None
        if require_current and not isinstance(cur, dict):
            raise ValueError("Config active requise pour un merge sûr")
        data = copy.deepcopy(cur) if isinstance(cur, dict) else {}
        for key, path in setters.items():
            val = sig.get(key)
            if val is None:
                continue
            node = data
            for p in path[:-1]:
                sub = node.get(p)
                if not isinstance(sub, dict):
                    sub = {}
                    node[p] = sub
                node = sub
            node[path[-1]] = val
        return data

    return build


def signature_for_emit(sig: Dict[str, Any]) -> Dict[str, Any]:
    return dict(sig)


def build_ai_scalar_spec(
    *,
    scraper_name: str,
    config_key: str,
    ai_script_path: str,
    keys: List[str],
    setters: Dict[str, List[str]],
    comment: str,
    bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    source_key: Optional[str] = None,
    require_current: bool = True,
    validate: Optional[Callable[[Dict[str, Any]], ValidationResult]] = None,
    build: Optional[
        Callable[[Dict[str, Any], Optional[Dict[str, Any]]], Dict[str, Any]]
    ] = None,
) -> RateSpec:
    script_name = Path(ai_script_path).name
    return RateSpec(
        scraper_name=scraper_name,
        config_key=config_key,
        scripts=[ScraperScript(script_name, ai_script_path, blocking=True)],
        extract_signature=make_signature(keys),
        signatures_equal=make_signatures_equal(keys),
        validate_signature=validate or make_range_validator(bounds or {}),
        build_config_data=build or make_merge_builder(setters, require_current=require_current),
        persistence_mode=PersistenceMode.FULL,
        comment=comment,
        primary_label=script_name,
        dual_source_consensus=False,
        warn_single_source=True,
        signature_for_emit=signature_for_emit,
        source_key=source_key or scraper_name,
        tier="critical",
    )
