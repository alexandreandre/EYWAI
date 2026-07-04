"""Politique de pauses — normalisation multi-types (payées / non payées)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Sequence

BreakKind = Literal["short", "meal", "other"]

INDUSTRIAL_2X10_MEAL_30: tuple[dict[str, Any], ...] = (
    {"minutes": 10, "paid": True, "kind": "short"},
    {"minutes": 10, "paid": True, "kind": "short"},
    {"minutes": 30, "paid": False, "kind": "meal"},
)


def normalize_break_item(raw: dict[str, Any]) -> dict[str, Any]:
    kind = str(raw.get("kind") or "other").strip().lower()
    if kind not in ("short", "meal", "other"):
        kind = "other"
    minutes = int(raw.get("minutes") or 0)
    return {
        "minutes": max(0, minutes),
        "paid": bool(raw.get("paid", False)),
        "kind": kind,
    }


def compute_break_totals(breaks: Sequence[dict[str, Any]]) -> tuple[int, int, int]:
    """Retourne (total, paid_minutes, unpaid_minutes)."""
    paid = 0
    unpaid = 0
    for item in breaks:
        norm = normalize_break_item(item)
        if norm["paid"]:
            paid += norm["minutes"]
        else:
            unpaid += norm["minutes"]
    return paid + unpaid, paid, unpaid


def breaks_from_legacy(break_minutes: int, break_paid: bool) -> list[dict[str, Any]]:
    if break_minutes <= 0:
        return []
    return [
        {
            "minutes": int(break_minutes),
            "paid": bool(break_paid),
            "kind": "meal" if not break_paid else "other",
        }
    ]


def resolve_breaks(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Résout breaks[] ou dérive depuis break_minutes / break_paid legacy."""
    raw_breaks = raw.get("breaks")
    if isinstance(raw_breaks, list) and raw_breaks:
        return [normalize_break_item(b) for b in raw_breaks if isinstance(b, dict)]
    legacy_min = int(raw.get("break_minutes") or 0)
    legacy_paid = bool(raw.get("break_paid", False))
    return breaks_from_legacy(legacy_min, legacy_paid)


def enrich_day_config_breaks(cfg: dict[str, Any]) -> dict[str, Any]:
    """Ajoute breaks[] et totaux dérivés à une config jour normalisée."""
    breaks = resolve_breaks(cfg)
    total, paid, unpaid = compute_break_totals(breaks)
    out = dict(cfg)
    out["breaks"] = breaks
    out["paid_break_minutes"] = paid
    out["unpaid_break_minutes"] = unpaid
    # Alias legacy : somme totale ; break_paid = toutes payées si total > 0
    out["break_minutes"] = total if total > 0 else int(cfg.get("break_minutes") or 0)
    if breaks:
        out["break_paid"] = paid > 0 and unpaid == 0
    return out


__all__ = [
    "INDUSTRIAL_2X10_MEAL_30",
    "BreakKind",
    "breaks_from_legacy",
    "compute_break_totals",
    "enrich_day_config_breaks",
    "normalize_break_item",
    "resolve_breaks",
]
