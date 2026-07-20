"""Diagnostic des écarts et propositions de remediation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.modules.payroll.backtest.models import (
    DiscrepancyReport,
    ReferenceBulletin,
    RemediationColor,
    RemediationProposal,
    Verdict,
)

# Catalogue de patterns (extensible, persiste sur disque)
DEFAULT_PATTERNS: List[Dict[str, Any]] = [
    {
        "id": "participation_missing",
        "description": "Participation absente dans monthly_inputs",
        "color": "VERT",
        "action_type": "monthly_input_participation",
        "confidence": 0.95,
        "signature": {"field": "participation", "delta_sign": "negative"},
    },
    {
        "id": "acompte_missing",
        "description": "Acompte participation absent",
        "color": "VERT",
        "action_type": "monthly_input_acompte",
        "confidence": 0.92,
        "signature": {"field": "acompte_participation", "delta_sign": "positive"},
    },
    {
        "id": "note_de_frais_missing",
        "description": "Remboursement note de frais absent",
        "color": "VERT",
        "action_type": "monthly_input_note_de_frais",
        "confidence": 0.90,
        "signature": {"field": "note_de_frais", "delta_sign": "negative"},
    },
    {
        "id": "prevoyance_inactive",
        "description": "Prévoyance GAN non activée (specificites_paie.prevoyance.adhesion)",
        "color": "VERT",
        "action_type": "enable_prevoyance",
        "confidence": 0.88,
        "signature": {"field": "prevoyance_gan", "delta_sign": "negative"},
    },
    {
        "id": "hors_hs_structurelles",
        "description": "Mode salaire_hors_hs_structurelles absent",
        "color": "VERT",
        "action_type": "enable_hors_hs",
        "confidence": 0.85,
        "signature": {"field": "prime_anciennete", "delta_sign": "any"},
    },
    {
        "id": "brut_absences_fictives",
        "description": "Écart brut probablement lié au pointage (absences fictives)",
        "color": "VERT",
        "action_type": "align_pointage_planning",
        "confidence": 0.80,
        "signature": {"field": "salaire_brut", "delta_sign": "negative", "min_abs_delta": 50},
    },
    {
        "id": "classification_coeff",
        "description": "Coefficient conventionnel manquant ou incorrect",
        "color": "VERT",
        "action_type": "set_classification",
        "confidence": 0.75,
        "signature": {"field": "salaire_brut", "delta_sign": "any", "min_abs_delta": 5},
    },
    {
        "id": "fillon_systemic",
        "description": "Écart réduction générale Fillon (systémique)",
        "color": "ORANGE",
        "action_type": "code_fix_fillon",
        "confidence": 0.70,
        "signature": {"field": "cout_total_employeur", "delta_sign": "any", "systemic": True},
    },
    {
        "id": "mns_calculation",
        "description": "Écart MNS / net avant impôt (moteur)",
        "color": "ORANGE",
        "action_type": "code_fix_mns",
        "confidence": 0.65,
        "signature": {"field": "montant_net_social", "delta_sign": "any"},
    },
]


def load_pattern_catalog(catalog_path: Path | None = None) -> List[Dict[str, Any]]:
    if catalog_path and catalog_path.exists():
        data = json.loads(catalog_path.read_text(encoding="utf-8"))
        return data.get("patterns", DEFAULT_PATTERNS)
    return list(DEFAULT_PATTERNS)


def save_pattern_catalog(patterns: List[Dict[str, Any]], catalog_path: Path) -> None:
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(
        json.dumps({"patterns": patterns}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def diagnose_reports(
    reports: List[DiscrepancyReport],
    references: Dict[str, ReferenceBulletin],
    *,
    catalog_path: Path | None = None,
    systemic_fields: set[str] | None = None,
) -> List[RemediationProposal]:
    patterns = load_pattern_catalog(catalog_path)
    systemic_fields = systemic_fields or set()
    proposals: Dict[str, RemediationProposal] = {}

    for report in reports:
        if report.overall_verdict in (Verdict.PARFAIT, Verdict.OK, Verdict.TOLERE, Verdict.KNOWN_GAP):
            continue
        ref = references.get(report.matricule)
        for line in report.lines:
            if line.verdict not in (Verdict.ANOMALIE, Verdict.QUARANTAINE):
                continue
            for pattern in patterns:
                if not _matches_pattern(line, pattern, systemic_fields):
                    continue
                pid = pattern["id"]
                if pid not in proposals:
                    proposals[pid] = RemediationProposal(
                        pattern_id=pid,
                        color=RemediationColor(pattern["color"]),
                        description=pattern["description"],
                        confidence=pattern["confidence"],
                        action_type=pattern["action_type"],
                        payload=_build_payload(pattern, line, ref),
                    )
                if report.matricule not in proposals[pid].affected_matricules:
                    proposals[pid].affected_matricules.append(report.matricule)

    return sorted(proposals.values(), key=lambda p: (-p.confidence, p.pattern_id))


def _matches_pattern(
    line: Any,
    pattern: Dict[str, Any],
    systemic_fields: set[str],
) -> bool:
    sig = pattern.get("signature") or {}
    if sig.get("field") and sig["field"] != line.field_key:
        return False
    if sig.get("systemic") and line.field_key not in systemic_fields:
        return False
    sign = sig.get("delta_sign", "any")
    if sign == "negative" and line.delta >= 0:
        return False
    if sign == "positive" and line.delta <= 0:
        return False
    min_delta = sig.get("min_abs_delta", 0)
    if abs(line.delta) < min_delta:
        return False
    return True


def _build_payload(
    pattern: Dict[str, Any],
    line: Any,
    ref: ReferenceBulletin | None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "field_key": line.field_key,
        "reference_value": line.reference_value,
        "actual_value": line.actual_value,
        "delta": line.delta,
    }
    if ref:
        if pattern["action_type"] == "monthly_input_participation":
            for rub in ref.rubriques:
                if "participation" in rub.libelle.lower() and rub.montant_salarial:
                    payload["amount"] = rub.montant_salarial
        elif pattern["action_type"] == "monthly_input_acompte":
            for rub in ref.rubriques:
                if "acompte" in rub.libelle.lower() and rub.montant_salarial:
                    payload["amount"] = abs(rub.montant_salarial)
        elif pattern["action_type"] == "monthly_input_note_de_frais":
            for rub in ref.rubriques:
                if "note de frais" in rub.libelle.lower() and rub.montant_salarial:
                    payload["amount"] = rub.montant_salarial
        elif pattern["action_type"] == "set_classification" and ref.coefficient:
            payload["coefficient"] = ref.coefficient
    return payload
