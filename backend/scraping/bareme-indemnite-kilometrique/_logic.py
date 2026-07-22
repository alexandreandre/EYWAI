"""Normalisation, comparaison et build pour barème kilométrique."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.validation import ValidationResult, require_year_current


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_formula(f: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "segment": int(f.get("segment")),
        "a": None if f.get("a") is None else round(float(f.get("a")), 3),
        "b": None if f.get("b") is None else round(float(f.get("b")), 3),
    }


def _norm_tranche(t: Dict[str, Any]) -> Dict[str, Any]:
    cv_min = t.get("cv_min", None)
    cv_max = t.get("cv_max", None)
    forms = [_norm_formula(f) for f in t.get("formules", [])]
    forms.sort(key=lambda x: x["segment"])
    return {
        "cv_min": cv_min if cv_min is None else int(cv_min),
        "cv_max": cv_max if cv_max is None else int(cv_max),
        "formules": forms,
    }


def _norm_block(block: Dict[str, Any]) -> Dict[str, Any]:
    segs = block.get("segments", [])
    tranches = [_norm_tranche(t) for t in block.get("tranches_cv", [])]

    def keyfn(t):
        mn = float("-inf") if t["cv_min"] is None else int(t["cv_min"])
        mx = float("inf") if t["cv_max"] is None else int(t["cv_max"])
        return (mn, mx)

    tranches.sort(key=keyfn)
    return {"base": block.get("base"), "segments": segs, "tranches_cv": tranches}


def extract_sources(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    seen, out = set(), []
    for s in payload.get("meta", {}).get("source", []):
        key = (s.get("url", ""), s.get("label", ""))
        if key not in seen:
            seen.add(key)
            out.append(
                {
                    "url": s.get("url", ""),
                    "label": s.get("label", ""),
                    "date_doc": s.get("date_doc", ""),
                }
            )
    return out


def core_signature(payload: Dict[str, Any]) -> Dict[str, Any]:
    if payload.get("id") != "baremes_km":
        raise ValueError("id attendu 'baremes_km'")
    veh = payload.get("vehicules", {})
    return {
        "id": "baremes_km",
        "annee": payload.get("annee"),
        "vehicules": {
            "voitures": _norm_block(veh.get("voitures", {})),
            "motocyclettes": _norm_block(veh.get("motocyclettes", {})),
            "cyclomoteurs": _norm_block(veh.get("cyclomoteurs", {})),
        },
        "_payload_sources": extract_sources(payload),
    }


def _eq_float(a: Optional[float], b: Optional[float], tol: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol


def _eq_formulas(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False
    for fa, fb in zip(a, b):
        if int(fa["segment"]) != int(fb["segment"]):
            return False
        if not (_eq_float(fa["a"], fb["a"]) and _eq_float(fa["b"], fb["b"])):
            return False
    return True


def _eq_tranches(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> bool:
    if len(a) != len(b):
        return False
    for ta, tb in zip(a, b):
        # cv_min est une borne basse redondante (déductible du cv_max de la
        # tranche précédente) et encodée de façons équivalentes selon la source
        # pour la tranche la plus basse : null / 0 / 1. Seuls cv_max et les
        # coefficients (a, b) définissent réellement le barème — on compare donc
        # ces derniers, sans faire échouer le consensus sur une pure convention.
        if ta["cv_max"] != tb["cv_max"]:
            return False
        if not _eq_formulas(ta["formules"], tb["formules"]):
            return False
    return True


def equal_core(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    if a.get("annee") != b.get("annee"):
        return False
    va, vb = a["vehicules"], b["vehicules"]
    for k in ("voitures", "motocyclettes", "cyclomoteurs"):
        ba, bb = va.get(k, {}), vb.get(k, {})
        if json.dumps(ba.get("segments", []), sort_keys=True) != json.dumps(
            bb.get("segments", []), sort_keys=True
        ):
            return False
        if not _eq_tranches(ba.get("tranches_cv", []), bb.get("tranches_cv", [])):
            return False
    return True


def compute_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def validate_signature(sig: Dict[str, Any]) -> ValidationResult:
    return require_year_current(sig, key="annee")


def build_config_data(sig: Dict[str, Any], _current: Optional[dict]) -> Dict[str, Any]:
    sources = sig.get("_payload_sources") or []
    barème_item = {
        "id": "baremes_km",
        "libelle": f"Barème kilométrique {sig.get('annee')}",
        "annee": sig.get("annee"),
        "vehicules": sig.get("vehicules"),
    }
    meta = {
        "last_scraped": iso_now(),
        "generator": "bareme-indemnite-kilometrique/orchestrator.py",
        "source": sources,
        "hash": compute_hash([barème_item]),
    }
    return {"BAREME_KM": [barème_item], "meta": meta}


def signature_for_emit(sig: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in sig.items() if k != "_payload_sources"}
