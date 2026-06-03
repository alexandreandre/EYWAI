"""Helpers pour les orchestrateurs de cotisations (patch payroll_config.cotisations)."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from cotisation_sync import (
    new_cotisation_item,
    should_apply_cotisation_patch,
    stamp_cotisation_inplace,
)


def payload_sections(payload: dict) -> dict:
    """Signature depuis sections ou valeurs (rétrocompat)."""
    if "sections" in payload and payload["sections"]:
        return payload["sections"]
    return payload.get("valeurs") or {}


def patch_cotisation_fields(
    current_config_data: Optional[dict],
    *,
    patches: list[tuple[str, dict]],
    default_new_items: dict[str, dict] | None = None,
) -> dict:
    """
    patches: liste (cotisation_id, champs à fusionner sur l'item).
    default_new_items: modèles si l'item n'existe pas.
    """
    if current_config_data:
        new_data = json.loads(json.dumps(current_config_data))
    else:
        new_data = {"cotisations": []}

    cotisations: list = new_data.setdefault("cotisations", [])
    default_new_items = default_new_items or {}

    for cot_id, fields in patches:
        if not should_apply_cotisation_patch(cot_id):
            continue
        found = False
        for item in cotisations:
            if isinstance(item, dict) and item.get("id") == cot_id:
                found = True
                item.update(fields)
                stamp_cotisation_inplace(item, cot_id)
                break
        if not found and cot_id in default_new_items:
            base = {**default_new_items[cot_id], **fields}
            cotisations.append(new_cotisation_item(base, cot_id))

    return new_data


def equal_sections_keys(
    a: dict,
    b: dict,
    keys: list[str],
    *,
    abs_tol: float = 1e-9,
) -> bool:
    import math

    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            return False
        if not math.isclose(float(va), float(vb), rel_tol=0.0, abs_tol=abs_tol):
            return False
    return True
