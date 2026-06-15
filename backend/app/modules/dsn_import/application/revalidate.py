"""Revalidation preview après éditions utilisateur."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.dsn_import.application.mapping import build_actions_summary
from app.shared.dsn_validation import validate_nir_dsn, validate_siret, validate_siren


def _merge_payload(
    base: Dict[str, Any], edits: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    out = dict(base or {})
    if edits:
        out.update(edits)
    return out


def validate_payload_edits(
    items: List[Dict[str, Any]], payload_edits: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Anomalies supplémentaires liées aux edits utilisateur."""
    extra: List[Dict[str, Any]] = []
    for it in items:
        ref = it.get("source_ref", "")
        edits = payload_edits.get(ref) or {}
        if not edits:
            continue
        payload = _merge_payload(it.get("mapped_payload") or {}, edits)
        item_type = it.get("item_type")
        label = it.get("label") or ref

        if item_type == "group":
            siren = str(payload.get("siren") or "")
            ok, err = validate_siren(siren)
            if not ok:
                extra.append(_anomaly(f"Groupe : {err}", "blocking", ref))
        elif item_type == "establishment":
            siret = str(payload.get("siret") or "")
            ok, err = validate_siret(siret)
            if not ok:
                extra.append(_anomaly(f"{label} : {err}", "blocking", ref))
        elif item_type == "employee":
            nir = str(payload.get("nir") or "")
            if nir:
                ok, err = validate_nir_dsn(nir)
                if not ok:
                    extra.append(_anomaly(f"{label} : {err}", "blocking", ref))

    return extra


def _anomaly(message: str, severity: str, source_ref: str) -> Dict[str, Any]:
    return {
        "type": "error" if severity == "blocking" else "warning",
        "message": message,
        "severity": severity,
        "source_ref": source_ref,
    }


def revalidate_batch_preview(
    batch: Dict[str, Any],
    items: List[Dict[str, Any]],
    payload_edits: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Recalcule anomalies et can_commit à partir du batch stocké + edits."""
    payload_edits = payload_edits or {}
    preview = batch.get("preview") or {}
    base_anomalies = list(preview.get("anomalies") or [])

    edit_anomalies = validate_payload_edits(items, payload_edits)

    edited_refs = set(payload_edits.keys())
    filtered_base = [
        a
        for a in base_anomalies
        if not (a.get("source_ref") in edited_refs and a.get("severity") == "blocking")
    ]

    all_anomalies = filtered_base + edit_anomalies
    can_commit = not any(a.get("severity") == "blocking" for a in all_anomalies)

    summary = dict(batch.get("summary") or {})
    non_cumul = [it for it in items if it.get("item_type") != "cumul"]
    summary["actions_summary"] = build_actions_summary(non_cumul)

    return {
        "anomalies": all_anomalies,
        "can_commit": can_commit,
        "summary": summary,
    }
