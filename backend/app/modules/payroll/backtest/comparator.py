"""Comparateur multi-tiers EYWAI vs référentiel Cegid."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.modules.payroll.backtest.models import (
    DiscrepancyLine,
    DiscrepancyReport,
    ReferenceBulletin,
    Verdict,
)
from app.modules.payroll.backtest.rubric_map import extract_eywai_metrics, reference_metrics
from app.modules.payroll.backtest.thresholds import FIELD_TIERS, ThresholdConfig, default_thresholds

METRIC_LABELS: Dict[str, str] = {
    "salaire_brut": "Salaire brut",
    "net_a_payer": "Net à payer",
    "net_imposable": "Net imposable",
    "montant_net_social": "Montant net social",
    "net_avant_impot": "Net avant impôt",
    "pas_montant": "Prélèvement à la source",
    "pas_taux": "Taux PAS",
    "total_cotisations_salariales": "Total cotisations salariales",
    "total_cotisations_patronales": "Total cotisations patronales",
    "cout_total_employeur": "Coût total employeur",
    "participation": "Participation",
    "prime_anciennete": "Prime ancienneté",
    "prime_exceptionnelle": "Prime exceptionnelle",
    "prevoyance_gan": "Prévoyance GAN",
    "mutuelle_gan": "Mutuelle GAN",
    "acompte_participation": "Acompte participation",
    "note_de_frais": "Note de frais",
    "acompte_participation": "Acompte participation",
    "journee_solidarite": "Journée solidarité",
}


def _overall_verdict(lines: List[DiscrepancyLine]) -> Verdict:
    if not lines:
        return Verdict.PARFAIT
    if any(ln.verdict == Verdict.QUARANTAINE for ln in lines):
        return Verdict.QUARANTAINE
    if any(ln.verdict == Verdict.ANOMALIE and ln.tier == "S" for ln in lines):
        return Verdict.ANOMALIE
    if any(ln.verdict == Verdict.ANOMALIE for ln in lines):
        return Verdict.ANOMALIE
    if any(ln.verdict == Verdict.TOLERE for ln in lines):
        return Verdict.TOLERE
    if all(ln.verdict in (Verdict.PARFAIT, Verdict.OK, Verdict.KNOWN_GAP) for ln in lines):
        if any(ln.verdict == Verdict.OK for ln in lines):
            return Verdict.OK
        return Verdict.PARFAIT
    return Verdict.OK


def compare_bulletins(
    payslip_data: Dict[str, Any],
    reference: ReferenceBulletin,
    *,
    employee_id: str | None = None,
    employee_name: str = "",
    thresholds: ThresholdConfig | None = None,
    systemic_deltas: Dict[str, float] | None = None,
    correction_attempts: int = 0,
) -> DiscrepancyReport:
    cfg = thresholds or default_thresholds()
    actual = extract_eywai_metrics(payslip_data)
    ref = reference_metrics(reference)
    systemic_deltas = systemic_deltas or {}

    all_keys = set(actual.keys()) | set(ref.keys())
    priority_keys = [
        "salaire_brut",
        "net_a_payer",
        "net_imposable",
        "montant_net_social",
        "pas_montant",
        "participation",
        "prime_anciennete",
        "prime_exceptionnelle",
        "acompte_participation",
        "note_de_frais",
        "prevoyance_gan",
        "mutuelle_gan",
        "total_cotisations_salariales",
        "total_cotisations_patronales",
        "cout_total_employeur",
    ]
    ordered_keys = priority_keys + sorted(k for k in all_keys if k not in priority_keys)

    lines: List[DiscrepancyLine] = []
    line_count = len(payslip_data.get("calcul_du_brut") or []) + len(
        (payslip_data.get("structure_cotisations") or {}).get("bloc_principales", {}).get(
            "lignes", []
        )
        if isinstance((payslip_data.get("structure_cotisations") or {}).get("bloc_principales"), dict)
        else []
    )
    agg_budget = cfg.aggregate_rounding_budget(line_count)

    for key in ordered_keys:
        ref_val = ref.get(key)
        act_val = actual.get(key)
        if ref_val is None and act_val is None:
            continue
        # Ne comparer que si la référence Cegid expose la valeur (sauf tier S toujours)
        tier = FIELD_TIERS.get(key, "B")
        if ref_val is None and tier not in ("S",):
            continue
        # Ignorer clés dérivées (_heures) sauf si explicitement suivies
        if key.endswith("_heures") and key not in priority_keys:
            continue
        if ref_val is None or act_val is None:
            if key in cfg.known_gap_fields:
                lines.append(
                    DiscrepancyLine(
                        field_key=key,
                        label=METRIC_LABELS.get(key, key),
                        tier=FIELD_TIERS.get(key, "C"),
                        reference_value=ref_val,
                        actual_value=act_val,
                        delta=0.0,
                        tolerance=0.0,
                        verdict=Verdict.KNOWN_GAP,
                        notes="Champ connu non implémenté ou absent d'un côté",
                    )
                )
                continue
            # Référence présente mais absent côté EYWAI → anomalie tier A/S
            missing_delta = -(ref_val or 0.0) if act_val is None else (act_val or 0.0)
            tier = FIELD_TIERS.get(key, "A")
            tolerance = cfg.tolerance(tier, ref_val or act_val)
            lines.append(
                DiscrepancyLine(
                    field_key=key,
                    label=METRIC_LABELS.get(key, key.replace("_", " ").title()),
                    tier=tier,
                    reference_value=ref_val,
                    actual_value=act_val,
                    delta=round(missing_delta, 2),
                    tolerance=tolerance,
                    verdict=Verdict.ANOMALIE,
                    notes="Valeur absente côté EYWAI" if act_val is None else "Valeur absente côté référence",
                )
            )
            continue

        delta = round((act_val or 0.0) - (ref_val or 0.0), 2)
        tier = FIELD_TIERS.get(key, "B")
        tolerance = cfg.tolerance(tier, ref_val)
        if tier == "C":
            tolerance = max(tolerance, agg_budget)

        verdict = _classify(delta, tolerance, key, cfg, systemic_deltas)
        lines.append(
            DiscrepancyLine(
                field_key=key,
                label=METRIC_LABELS.get(key, key.replace("_", " ").title()),
                tier=tier,
                reference_value=ref_val,
                actual_value=act_val,
                delta=delta,
                tolerance=tolerance,
                verdict=verdict,
                is_systemic=key in systemic_deltas,
                notes="Écart systémique détecté" if key in systemic_deltas else "",
            )
        )

    tier_s_max = max(
        (abs(ln.delta) for ln in lines if ln.tier == "S"),
        default=0.0,
    )
    report = DiscrepancyReport(
        matricule=reference.matricule,
        employee_id=employee_id,
        employee_name=employee_name,
        lines=lines,
        overall_verdict=_overall_verdict(lines),
        tier_s_max_delta=tier_s_max,
        correction_attempts=correction_attempts,
    )
    return report


def _classify(
    delta: float,
    tolerance: float,
    field_key: str,
    cfg: ThresholdConfig,
    systemic_deltas: Dict[str, float],
) -> Verdict:
    if field_key in cfg.known_gap_fields:
        return Verdict.KNOWN_GAP
    if field_key in systemic_deltas:
        if abs(delta - systemic_deltas[field_key]) <= cfg.systemic_delta_match_eur:
            return Verdict.TOLERE
    if abs(delta) <= tolerance:
        tier = FIELD_TIERS.get(field_key, "B")
        if abs(delta) <= cfg.tolerance("S", 0) and tier == "S":
            return Verdict.PARFAIT
        return Verdict.OK
    return Verdict.ANOMALIE


def detect_systemic_deltas(
    reports: List[DiscrepancyReport],
    cfg: ThresholdConfig | None = None,
) -> Dict[str, float]:
    """Détecte les écarts identiques partagés par >= N salariés."""
    cfg = cfg or default_thresholds()
    counts: Dict[str, Dict[float, int]] = {}
    for report in reports:
        for line in report.lines:
            if line.verdict != Verdict.ANOMALIE:
                continue
            bucket = counts.setdefault(line.field_key, {})
            rounded = round(line.delta, 2)
            bucket[rounded] = bucket.get(rounded, 0) + 1

    systemic: Dict[str, float] = {}
    for field_key, delta_counts in counts.items():
        for delta_val, count in delta_counts.items():
            if count >= cfg.systemic_min_employees:
                systemic[field_key] = delta_val
    return systemic
