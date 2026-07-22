"""Comparateur métier DSN référence vs actuelle."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.dsn_compare.domain.matcher import (
    EstablishmentMatch,
    MatchResult,
    match_establishments,
)
from app.modules.dsn_compare.domain.normalizer import (
    DsnNormalizedSnapshot,
    EmployeeSnap,
    normalize_dsn_bytes,
)
from app.modules.payroll.backtest.thresholds import ThresholdConfig, default_thresholds


@dataclass
class DiffLine:
    domain: str
    field: str
    tier: str
    ref: Any
    act: Any
    delta: float
    tolerance: float
    verdict: str
    notes: str = ""


@dataclass
class EmployeeComparison:
    employee_key: str
    match_method: str
    quarantine: bool
    overall_verdict: str
    lines: List[DiffLine] = field(default_factory=list)


@dataclass
class EstablishmentComparison:
    siret: str
    period: str
    norme_ref: str
    norme_act: str
    headcount_ref: int
    headcount_act: int
    brut_ref: float
    brut_act: float
    matched_count: int
    unmatched_ref: List[str]
    unmatched_act: List[str]
    summary_lines: List[DiffLine] = field(default_factory=list)
    employees: List[EmployeeComparison] = field(default_factory=list)


@dataclass
class DsnComparisonReport:
    meta: Dict[str, Any]
    establishments: List[EstablishmentComparison] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta,
            "warnings": self.warnings,
            "establishments": [asdict(e) for e in self.establishments],
        }


def _verdict(delta: float, tolerance: float, *, known_gap: bool = False) -> str:
    if known_gap:
        return "KNOWN_GAP"
    if abs(delta) <= 1e-9:
        return "PARFAIT"
    if abs(delta) <= tolerance:
        return "OK" if abs(delta) <= max(tolerance * 0.5, 0.01) else "TOLERE"
    return "ANOMALIE"


def _num_diff(
    domain: str,
    field: str,
    tier: str,
    ref: float,
    act: float,
    thresholds: ThresholdConfig,
    notes: str = "",
) -> DiffLine:
    delta = round(float(act) - float(ref), 4)
    tol = thresholds.tolerance(tier, ref)
    return DiffLine(
        domain=domain,
        field=field,
        tier=tier,
        ref=round(float(ref), 4),
        act=round(float(act), 4),
        delta=delta,
        tolerance=tol,
        verdict=_verdict(delta, tol),
        notes=notes,
    )


def _worst(verdicts: List[str]) -> str:
    order = ["ANOMALIE", "QUARANTAINE", "KNOWN_GAP", "TOLERE", "OK", "PARFAIT"]
    for v in order:
        if v in verdicts:
            return v
    return "PARFAIT"


def compare_employees(
    ref: EmployeeSnap,
    act: EmployeeSnap,
    *,
    match_method: str,
    quarantine: bool,
    thresholds: ThresholdConfig,
) -> EmployeeComparison:
    lines: List[DiffLine] = []
    lines.append(
        _num_diff("totaux", "brut", "S", ref.brut, act.brut, thresholds)
    )
    lines.append(
        _num_diff(
            "totaux",
            "net_imposable",
            "S",
            ref.net_imposable,
            act.net_imposable,
            thresholds,
        )
    )
    lines.append(
        _num_diff("totaux", "pas", "S", ref.pas, act.pas, thresholds)
    )
    lines.append(
        _num_diff("totaux", "heures", "A", ref.heures, act.heures, thresholds)
    )
    if ref.net_verse or act.net_verse:
        lines.append(
            _num_diff(
                "totaux",
                "net_verse",
                "S",
                ref.net_verse,
                act.net_verse,
                thresholds,
            )
        )

    # Identité / contrat (informatif sauf nature)
    if ref.nature_contrat and act.nature_contrat and ref.nature_contrat != act.nature_contrat:
        lines.append(
            DiffLine(
                domain="contrat",
                field="nature",
                tier="A",
                ref=ref.nature_contrat,
                act=act.nature_contrat,
                delta=0,
                tolerance=0,
                verdict="ANOMALIE",
                notes="Nature de contrat différente",
            )
        )

    # Rémunérations par type
    ref_rems = {r.type_code: r for r in ref.remunerations if r.type_code}
    act_rems = {r.type_code: r for r in act.remunerations if r.type_code}
    for code in sorted(set(ref_rems) | set(act_rems)):
        r = ref_rems.get(code)
        a = act_rems.get(code)
        lines.append(
            _num_diff(
                "remuneration",
                f"type_{code}",
                "A" if code in {"001", "002", "003", "010"} else "B",
                r.montant if r else 0.0,
                a.montant if a else 0.0,
                thresholds,
            )
        )

    # Cotisations par code
    ref_cots: Dict[str, float] = {}
    act_cots: Dict[str, float] = {}
    for c in ref.cotisations:
        ref_cots[c.code] = ref_cots.get(c.code, 0.0) + c.montant
    for c in act.cotisations:
        act_cots[c.code] = act_cots.get(c.code, 0.0) + c.montant
    for code in sorted(set(ref_cots) | set(act_cots)):
        lines.append(
            _num_diff(
                "cotisation",
                f"code_{code}",
                "B",
                ref_cots.get(code, 0.0),
                act_cots.get(code, 0.0),
                thresholds,
            )
        )

    # Bases
    for code in sorted(set(ref.bases) | set(act.bases)):
        lines.append(
            _num_diff(
                "base",
                f"code_{code}",
                "B",
                ref.bases.get(code, 0.0),
                act.bases.get(code, 0.0),
                thresholds,
            )
        )

    # Événements : présence
    ref_ev = {(e.get("type"), e.get("debut"), e.get("motif")) for e in ref.events}
    act_ev = {(e.get("type"), e.get("debut"), e.get("motif")) for e in act.events}
    only_ref = ref_ev - act_ev
    only_act = act_ev - ref_ev
    if only_ref or only_act:
        lines.append(
            DiffLine(
                domain="evenements",
                field="liste",
                tier="A",
                ref=sorted(list(only_ref)),
                act=sorted(list(only_act)),
                delta=float(len(only_ref) + len(only_act)),
                tolerance=0,
                verdict="ANOMALIE" if (only_ref or only_act) else "PARFAIT",
                notes="Écarts d'événements (arrêts / suspensions / fins)",
            )
        )

    verdicts = [ln.verdict for ln in lines]
    if quarantine:
        verdicts.append("QUARANTAINE")
    return EmployeeComparison(
        employee_key=ref.key,
        match_method=match_method,
        quarantine=quarantine,
        overall_verdict=_worst(verdicts),
        lines=lines,
    )


def compare_establishment(
    est_match: EstablishmentMatch,
    thresholds: ThresholdConfig,
) -> EstablishmentComparison:
    summary = [
        _num_diff(
            "etablissement",
            "brut",
            "S",
            est_match.ref.brut,
            est_match.act.brut,
            thresholds,
        ),
        _num_diff(
            "etablissement",
            "net_imposable",
            "S",
            est_match.ref.net_imposable,
            est_match.act.net_imposable,
            thresholds,
        ),
        _num_diff(
            "etablissement",
            "pas",
            "S",
            est_match.ref.pas,
            est_match.act.pas,
            thresholds,
        ),
        _num_diff(
            "etablissement",
            "headcount",
            "C",
            float(est_match.ref.headcount),
            float(est_match.act.headcount),
            thresholds,
        ),
    ]
    employees: List[EmployeeComparison] = []
    for m in est_match.matched:
        ref_emp = est_match.ref.employees[m.ref_key]
        act_emp = est_match.act.employees[m.act_key]
        employees.append(
            compare_employees(
                ref_emp,
                act_emp,
                match_method=m.method,
                quarantine=m.quarantine,
                thresholds=thresholds,
            )
        )
    return EstablishmentComparison(
        siret=est_match.siret,
        period=est_match.ref.period or est_match.act.period,
        norme_ref=est_match.ref.norme,
        norme_act=est_match.act.norme,
        headcount_ref=est_match.ref.headcount,
        headcount_act=est_match.act.headcount,
        brut_ref=est_match.ref.brut,
        brut_act=est_match.act.brut,
        matched_count=len(est_match.matched),
        unmatched_ref=list(est_match.unmatched_ref),
        unmatched_act=list(est_match.unmatched_act),
        summary_lines=summary,
        employees=employees,
    )


def compare_snapshots(
    ref: DsnNormalizedSnapshot,
    act: DsnNormalizedSnapshot,
    *,
    thresholds: Optional[ThresholdConfig] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> DsnComparisonReport:
    thr = thresholds or default_thresholds()
    match: MatchResult = match_establishments(ref.establishments, act.establishments)
    establishments = [compare_establishment(m, thr) for m in match.establishments]
    warnings = list(ref.warnings) + list(act.warnings)
    for siret in match.unmatched_ref_sirets:
        warnings.append(f"Établissement référence sans correspondant : {siret}")
    for siret in match.unmatched_act_sirets:
        warnings.append(f"Établissement actuel sans correspondant : {siret}")
    return DsnComparisonReport(
        meta=meta or {},
        establishments=establishments,
        warnings=warnings,
    )


def compare_dsn_bytes(
    reference: bytes,
    actual: bytes,
    *,
    reference_name: str = "reference.dsn",
    actual_name: str = "actual.dsn",
    thresholds: Optional[ThresholdConfig] = None,
) -> DsnComparisonReport:
    ref = normalize_dsn_bytes(reference, file_name=reference_name)
    act = normalize_dsn_bytes(actual, file_name=actual_name)
    return compare_snapshots(
        ref,
        act,
        thresholds=thresholds,
        meta={
            "reference_file": reference_name,
            "actual_file": actual_name,
        },
    )
