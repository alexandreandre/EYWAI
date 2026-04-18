"""
Moteur de comparaison N vs N-1 sur payslip_data (pur domaine, sans I/O).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

AlertLevel = Literal["CRITIQUE", "AVERTISSEMENT", "INFO"]


@dataclass
class PayslipAlert:
    rule_id: str
    level: AlertLevel
    message: str
    field: str
    value_n: float
    value_n1: float
    delta_pct: float
    status: str = "active"  # active | acquittee | ignoree
    acquitted_by: Optional[str] = None
    acquitted_at: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class ComparisonLine:
    libelle: str
    value_n: Optional[float]
    value_n1: Optional[float]
    delta_abs: Optional[float]
    delta_pct: Optional[float]
    alert_level: Optional[AlertLevel] = None


@dataclass
class ComparisonResult:
    bulletin_n_id: str
    bulletin_n1_id: Optional[str]
    month_n: int
    year_n: int
    month_n1: Optional[int]
    year_n1: Optional[int]
    lines: List[ComparisonLine] = field(default_factory=list)
    alerts: List[PayslipAlert] = field(default_factory=list)
    has_critical: bool = False


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _pct_change(old: float, new: float) -> float:
    if old == 0:
        return 0.0 if new == 0 else 100.0
    return 100.0 * (new - old) / old


def _libelles_brut(calcul_du_brut: Any) -> set[str]:
    out: set[str] = set()
    if not isinstance(calcul_du_brut, list):
        return out
    for line in calcul_du_brut:
        if not isinstance(line, dict):
            continue
        lib = line.get("libelle")
        if lib is None:
            continue
        s = str(lib).strip()
        if s:
            out.add(s)
    return out


def _sum_travail_base_hours(calcul_du_brut: Any) -> float:
    total = 0.0
    if not isinstance(calcul_du_brut, list):
        return total
    for line in calcul_du_brut:
        if not isinstance(line, dict):
            continue
        if line.get("type") != "travail_base":
            continue
        total += _to_float(line.get("quantite"))
    return total


def _extract_values(bulletin: Dict[str, Any]) -> Dict[str, float]:
    """Extrait les agrégats utiles depuis un payslip_data."""
    sc = bulletin.get("structure_cotisations") or {}
    if not isinstance(sc, dict):
        sc = {}
    sn = bulletin.get("synthese_net") or {}
    if not isinstance(sn, dict):
        sn = {}
    return {
        "salaire_brut": _to_float(bulletin.get("salaire_brut")),
        "net_a_payer": _to_float(bulletin.get("net_a_payer")),
        "total_cotisations_salariales": _to_float(sc.get("total_salarial")),
        "heures_travaillees": _sum_travail_base_hours(bulletin.get("calcul_du_brut")),
        "heures_supp": _to_float(bulletin.get("total_heures_supp")),
        "acompte_verse": _to_float(sn.get("acompte_verse")),
    }


def _apply_alerts_status_from_bulletin(
    alerts: List[PayslipAlert], alerts_status: Any
) -> None:
    if not isinstance(alerts_status, dict):
        return
    for a in alerts:
        entry = alerts_status.get(a.rule_id)
        if not isinstance(entry, dict):
            continue
        st = entry.get("status")
        if st in ("acquittee", "ignoree"):
            a.status = str(st)
            a.acquitted_by = entry.get("by") if isinstance(entry.get("by"), str) else None
            raw_at = entry.get("at")
            a.acquitted_at = str(raw_at) if raw_at is not None else None
            c = entry.get("comment")
            a.comment = str(c) if c is not None else None


def _reevaluate_has_critical(alerts: List[PayslipAlert]) -> bool:
    return any(a.level == "CRITIQUE" and a.status == "active" for a in alerts)


def compute_comparison(
    bulletin_n: Dict[str, Any],
    bulletin_n1: Optional[Dict[str, Any]],
    employee_context: Dict[str, Any] | None = None,
) -> ComparisonResult:
    """
    Compare les payslip_data N et N-1 et applique les règles R01–R12.

    Métadonnées attendues dans employee_context :
    - bulletin_n_id, month_n, year_n (obligatoires)
    - bulletin_n1_id, month_n1, year_n1 (si N-1 présent)
    - is_forfait_jour: bool
    - has_contract_change: bool
    - monthly_contract_hours: float (défaut 151.67)
    - has_declared_advance: bool — si False explicite avec acompte > 0 → R11
    - recent_nets_asc: liste [net_n-3, net_n-2, net_n-1, net_n] pour R10
    """
    ctx = employee_context or {}
    bulletin_n_id = str(ctx.get("bulletin_n_id", ""))
    month_n = int(ctx.get("month_n", 0))
    year_n = int(ctx.get("year_n", 0))
    bulletin_n1_id = ctx.get("bulletin_n1_id")
    month_n1 = ctx.get("month_n1")
    year_n1 = ctx.get("year_n1")

    vn = _extract_values(bulletin_n)
    v1 = _extract_values(bulletin_n1) if bulletin_n1 is not None else None

    lines: List[ComparisonLine] = []
    alerts: List[PayslipAlert] = []

    def add_line(
        libelle: str,
        key: str,
        alert_level: Optional[AlertLevel] = None,
    ) -> None:
        val_n = vn[key]
        val_n1 = v1[key] if v1 is not None else None
        d_abs = (val_n - val_n1) if val_n1 is not None else None
        d_pct = _pct_change(val_n1, val_n) if val_n1 is not None else None
        lines.append(
            ComparisonLine(
                libelle=libelle,
                value_n=val_n,
                value_n1=val_n1,
                delta_abs=d_abs,
                delta_pct=d_pct,
                alert_level=alert_level,
            )
        )

    is_forfait = bool(ctx.get("is_forfait_jour", False))
    has_contract_change = bool(ctx.get("has_contract_change", False))
    monthly_hours = _to_float(ctx.get("monthly_contract_hours", 151.67))

    # --- Lignes de synthèse ---
    add_line("Salaire brut", "salaire_brut")
    add_line("Net à payer", "net_a_payer")
    add_line("Cotisations salariales", "total_cotisations_salariales")
    add_line("Heures travaillées (travail_base)", "heures_travaillees")
    add_line("Heures supplémentaires", "heures_supp")
    add_line("Acompte versé", "acompte_verse")

    # --- R12 : N-1 absent ---
    if bulletin_n1 is None:
        alerts.append(
            PayslipAlert(
                rule_id="R12",
                level="INFO",
                message="Aucun bulletin N-1 validé trouvé pour la comparaison.",
                field="bulletin_n1",
                value_n=0.0,
                value_n1=0.0,
                delta_pct=0.0,
            )
        )

    if v1 is not None:
        d_brut = abs(_pct_change(v1["salaire_brut"], vn["salaire_brut"]))
        d_net = abs(_pct_change(v1["net_a_payer"], vn["net_a_payer"]))
        d_cot = abs(_pct_change(v1["total_cotisations_salariales"], vn["total_cotisations_salariales"]))

        # R01 / R02 — salaire brut
        if d_brut > 5.0 and not has_contract_change:
            alerts.append(
                PayslipAlert(
                    rule_id="R01",
                    level="CRITIQUE",
                    message=(
                        f"Le salaire brut de base a varié de {d_brut:.1f}% "
                        "sans modification de contrat détectée."
                    ),
                    field="salaire_brut",
                    value_n=vn["salaire_brut"],
                    value_n1=v1["salaire_brut"],
                    delta_pct=d_brut,
                )
            )
        elif 1.0 <= d_brut <= 5.0:
            alerts.append(
                PayslipAlert(
                    rule_id="R02",
                    level="AVERTISSEMENT",
                    message=(
                        f"Variation du salaire brut de {d_brut:.1f}% "
                        "(seuil d'avertissement 1–5 %)."
                    ),
                    field="salaire_brut",
                    value_n=vn["salaire_brut"],
                    value_n1=v1["salaire_brut"],
                    delta_pct=d_brut,
                )
            )

        # R03 / R04 — net à payer
        if d_net > 10.0:
            alerts.append(
                PayslipAlert(
                    rule_id="R03",
                    level="CRITIQUE",
                    message=(
                        f"Le net à payer a varié de {d_net:.1f}% "
                        "(seuil critique > 10 %)."
                    ),
                    field="net_a_payer",
                    value_n=vn["net_a_payer"],
                    value_n1=v1["net_a_payer"],
                    delta_pct=d_net,
                )
            )
        elif 5.0 <= d_net <= 10.0:
            alerts.append(
                PayslipAlert(
                    rule_id="R04",
                    level="AVERTISSEMENT",
                    message=(
                        f"Le net à payer a varié de {d_net:.1f}% "
                        "(seuil d'avertissement 5–10 %)."
                    ),
                    field="net_a_payer",
                    value_n=vn["net_a_payer"],
                    value_n1=v1["net_a_payer"],
                    delta_pct=d_net,
                )
            )

        # R05 — cotisations
        if d_cot > 8.0:
            alerts.append(
                PayslipAlert(
                    rule_id="R05",
                    level="AVERTISSEMENT",
                    message=(
                        f"Variation des cotisations salariales de {d_cot:.1f}% "
                        "(seuil > 8 %)."
                    ),
                    field="total_cotisations_salariales",
                    value_n=vn["total_cotisations_salariales"],
                    value_n1=v1["total_cotisations_salariales"],
                    delta_pct=d_cot,
                )
            )

        # R06 / R07 — libellés calcul_du_brut
        lib_n = _libelles_brut(bulletin_n.get("calcul_du_brut"))
        lib_n1 = _libelles_brut(bulletin_n1.get("calcul_du_brut") if bulletin_n1 else None)
        missing = sorted(lib_n1 - lib_n)
        new_ones = sorted(lib_n - lib_n1)
        if missing:
            alerts.append(
                PayslipAlert(
                    rule_id="R06",
                    level="AVERTISSEMENT",
                    message=(
                        "Éléments présents en N-1 absents en N : "
                        + ", ".join(missing)
                        + "."
                    ),
                    field="calcul_du_brut",
                    value_n=float(len(lib_n)),
                    value_n1=float(len(lib_n1)),
                    delta_pct=float(len(missing)),
                )
            )
        if new_ones:
            alerts.append(
                PayslipAlert(
                    rule_id="R07",
                    level="INFO",
                    message=(
                        "Nouveaux éléments de brut en N absents en N-1 : "
                        + ", ".join(new_ones)
                        + "."
                    ),
                    field="calcul_du_brut",
                    value_n=float(len(lib_n)),
                    value_n1=float(len(lib_n1)),
                    delta_pct=float(len(new_ones)),
                )
            )

    # R08 — heures travaillées vs contrat
    if not is_forfait and monthly_hours > 0:
        if vn["heures_travaillees"] < 0.5 * monthly_hours:
            alerts.append(
                PayslipAlert(
                    rule_id="R08",
                    level="CRITIQUE",
                    message=(
                        f"Heures travaillées ({vn['heures_travaillees']:.2f} h) "
                        f"inférieures à 50 % du volume contractuel ({monthly_hours:.2f} h)."
                    ),
                    field="heures_travaillees",
                    value_n=vn["heures_travaillees"],
                    value_n1=v1["heures_travaillees"] if v1 else 0.0,
                    delta_pct=_pct_change(
                        v1["heures_travaillees"], vn["heures_travaillees"]
                    )
                    if v1
                    else 0.0,
                )
            )

    # R09 — heures supp
    if vn["heures_supp"] > 20.0:
        alerts.append(
            PayslipAlert(
                rule_id="R09",
                level="INFO",
                message=(
                    f"Heures supplémentaires élevées : {vn['heures_supp']:.2f} h (> 20 h)."
                ),
                field="total_heures_supp",
                value_n=vn["heures_supp"],
                value_n1=v1["heures_supp"] if v1 else 0.0,
                delta_pct=_pct_change(v1["heures_supp"], vn["heures_supp"]) if v1 else 0.0,
            )
        )

    # R10 — baisse net 3 mois consécutifs
    recent = ctx.get("recent_nets_asc")
    if isinstance(recent, list) and len(recent) >= 4:
        nets = [_to_float(x) for x in recent[-4:]]
        if nets[3] < nets[2] < nets[1] < nets[0]:
            alerts.append(
                PayslipAlert(
                    rule_id="R10",
                    level="AVERTISSEMENT",
                    message=(
                        "Tendance à la baisse du net à payer sur trois mois consécutifs "
                        f"({nets[0]:.2f} → {nets[1]:.2f} → {nets[2]:.2f} → {nets[3]:.2f} €)."
                    ),
                    field="net_a_payer",
                    value_n=nets[3],
                    value_n1=nets[0],
                    delta_pct=_pct_change(nets[0], nets[3]),
                )
            )

    # R11 — acompte sans avance déclarée (clé explicite uniquement)
    if vn["acompte_verse"] > 0 and ctx.get("has_declared_advance") is False:
        alerts.append(
            PayslipAlert(
                rule_id="R11",
                level="CRITIQUE",
                message=(
                    f"Acompte déduit ({vn['acompte_verse']:.2f} €) "
                    "sans avance déclarée côté dossier."
                ),
                field="synthese_net.acompte_verse",
                value_n=vn["acompte_verse"],
                value_n1=v1["acompte_verse"] if v1 else 0.0,
                delta_pct=0.0,
            )
        )

    alerts_status = bulletin_n.get("alerts_status")
    _apply_alerts_status_from_bulletin(alerts, alerts_status)

    has_critical = _reevaluate_has_critical(alerts)

    return ComparisonResult(
        bulletin_n_id=bulletin_n_id,
        bulletin_n1_id=str(bulletin_n1_id) if bulletin_n1_id else None,
        month_n=month_n,
        year_n=year_n,
        month_n1=int(month_n1) if month_n1 is not None else None,
        year_n1=int(year_n1) if year_n1 is not None else None,
        lines=lines,
        alerts=alerts,
        has_critical=has_critical,
    )


def comparison_result_to_dict(result: ComparisonResult) -> dict[str, Any]:
    """Sérialisation plate pour FastAPI / Pydantic."""

    def alert_to_dict(a: PayslipAlert) -> dict[str, Any]:
        return {
            "rule_id": a.rule_id,
            "level": a.level,
            "message": a.message,
            "field": a.field,
            "value_n": a.value_n,
            "value_n1": a.value_n1,
            "delta_pct": a.delta_pct,
            "status": a.status,
            "acquitted_by": a.acquitted_by,
            "acquitted_at": a.acquitted_at,
            "comment": a.comment,
        }

    def line_to_dict(ln: ComparisonLine) -> dict[str, Any]:
        return {
            "libelle": ln.libelle,
            "value_n": ln.value_n,
            "value_n1": ln.value_n1,
            "delta_abs": ln.delta_abs,
            "delta_pct": ln.delta_pct,
            "alert_level": ln.alert_level,
        }

    return {
        "bulletin_n_id": result.bulletin_n_id,
        "bulletin_n1_id": result.bulletin_n1_id,
        "month_n": result.month_n,
        "year_n": result.year_n,
        "month_n1": result.month_n1,
        "year_n1": result.year_n1,
        "lines": [line_to_dict(x) for x in result.lines],
        "alerts": [alert_to_dict(x) for x in result.alerts],
        "has_critical": result.has_critical,
    }
