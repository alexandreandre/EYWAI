"""Notification mail de fin de campagne backtest."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.shared.infrastructure.email.smtp_sender import get_smtp_mail_sender

DEFAULT_RECIPIENT = "alexandreandre2004@gmail.com"


def build_report_markdown(
    *,
    company_name: str,
    year: int,
    month: int,
    state: Dict[str, Any],
    stop_reason: str,
    duration_minutes: float,
    patterns_applied: List[Dict[str, Any]],
    quarantines: List[Dict[str, Any]],
    tolerated: List[Dict[str, Any]],
) -> str:
    employees = state.get("employees") or {}
    converged = sum(
        1 for e in employees.values() if e.get("status") in ("PARFAIT", "OK", "TOLERE")
    )
    total = len(employees)
    lines = [
        f"# Backtest paie — {company_name} — {month:02d}/{year}",
        "",
        f"**Arrêt** : {stop_reason}",
        f"**Durée** : {duration_minutes:.1f} min",
        f"**Itérations** : {state.get('iteration', 0)}",
        f"**Convergence** : {converged}/{total} salariés",
        "",
        "## Patterns appliqués (auto)",
        "",
    ]
    if patterns_applied:
        for p in patterns_applied:
            lines.append(
                f"- `{p.get('pattern_id')}` → {len(p.get('matricules', []))} salarié(s)"
            )
    else:
        lines.append("- Aucun pattern appliqué cette campagne")

    lines.extend(["", "## Quarantaines", ""])
    if quarantines:
        for q in quarantines:
            lines.append(
                f"- **{q.get('name', q.get('matricule'))}** — "
                f"écart tier S max {q.get('tier_s_max_delta', '?')} € "
                f"({q.get('attempts', 0)} tentatives)"
            )
    else:
        lines.append("- Aucune quarantaine")

    lines.extend(["", "## Écarts tolérés (systémiques)", ""])
    if tolerated:
        for t in tolerated:
            lines.append(f"- `{t.get('field_key')}` : {t.get('delta')} € ({t.get('count')} sal.)")
    else:
        lines.append("- Aucun écart systémique documenté")

    lines.extend(["", "## Détail par salarié", ""])
    for matricule, info in sorted(employees.items()):
        lines.append(
            f"- **{matricule}** : {info.get('status')} "
            f"(tier S Δ={info.get('tier_s_max_delta', 0):.2f} €, "
            f"{info.get('anomaly_count', 0)} anomalie(s))"
        )
    return "\n".join(lines)


def send_campaign_email(
    *,
    company_name: str,
    year: int,
    month: int,
    state: Dict[str, Any],
    stop_reason: str,
    duration_minutes: float,
    report_path: Path,
    patterns_applied: List[Dict[str, Any]] | None = None,
    quarantines: List[Dict[str, Any]] | None = None,
    tolerated: List[Dict[str, Any]] | None = None,
    recipient: str = DEFAULT_RECIPIENT,
) -> tuple[bool, str | None]:
    employees = state.get("employees") or {}
    converged = sum(
        1 for e in employees.values() if e.get("status") in ("PARFAIT", "OK", "TOLERE")
    )
    total = len(employees)
    status_label = "CONVERGÉ" if converged == total and total > 0 else stop_reason.upper()

    report_md = build_report_markdown(
        company_name=company_name,
        year=year,
        month=month,
        state=state,
        stop_reason=stop_reason,
        duration_minutes=duration_minutes,
        patterns_applied=patterns_applied or [],
        quarantines=quarantines or state.get("quarantines") or [],
        tolerated=tolerated or [],
    )
    report_path.write_text(report_md, encoding="utf-8")

    subject = (
        f"[Backtest paie] {company_name} — {month:02d}/{year} — "
        f"{status_label} {converged}/{total}"
    )
    text = report_md
    html = f"<pre>{report_md}</pre>"

    sender = get_smtp_mail_sender()
    attachments = []
    if report_path.exists():
        attachments = [
            (report_path.name, report_path.read_bytes(), "text/markdown"),
        ]
    ok, err = sender.send_email_with_attachments(
        [recipient],
        subject,
        text,
        html,
        attachments,
    )
    return ok, err
