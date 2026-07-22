"""Rédaction de rapports JSON / Markdown pour la comparaison DSN."""

from __future__ import annotations

import json
from typing import Any, Dict

from app.modules.dsn_compare.application.comparator import DsnComparisonReport


def report_to_json(report: DsnComparisonReport, *, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=indent)


def report_to_markdown(report: DsnComparisonReport) -> str:
    lines: list[str] = []
    meta = report.meta or {}
    lines.append("# Comparaison DSN EYWAI vs référence")
    lines.append("")
    if meta:
        lines.append("## Meta")
        for k, v in meta.items():
            lines.append(f"- **{k}** : `{v}`")
        lines.append("")

    if report.warnings:
        lines.append("## Avertissements")
        for w in report.warnings:
            lines.append(f"- {w}")
        lines.append("")

    if not report.establishments:
        lines.append("_Aucun établissement apparié._")
        return "\n".join(lines) + "\n"

    for est in report.establishments:
        lines.append(f"## Établissement `{est.siret}` — {est.period}")
        lines.append("")
        lines.append(
            f"- Norme : ref `{est.norme_ref}` / act `{est.norme_act}`"
        )
        lines.append(
            f"- Effectifs : ref **{est.headcount_ref}** / act **{est.headcount_act}**"
        )
        lines.append(
            f"- Brut : ref **{est.brut_ref:.2f}** / act **{est.brut_act:.2f}**"
        )
        lines.append(f"- Salariés appariés : **{est.matched_count}**")
        if est.unmatched_ref:
            lines.append(
                f"- Non appariés (réf) : {len(est.unmatched_ref)} — "
                + ", ".join(est.unmatched_ref[:10])
            )
        if est.unmatched_act:
            lines.append(
                f"- Non appariés (act) : {len(est.unmatched_act)} — "
                + ", ".join(est.unmatched_act[:10])
            )
        lines.append("")
        lines.append("### Synthèse établissement")
        lines.append("")
        lines.append("| Champ | Tier | Réf | Act | Δ | Tol | Verdict |")
        lines.append("|---|---|---:|---:|---:|---:|---|")
        for ln in est.summary_lines:
            lines.append(
                f"| {ln.field} | {ln.tier} | {ln.ref} | {ln.act} | {ln.delta} | "
                f"{ln.tolerance} | **{ln.verdict}** |"
            )
        lines.append("")

        anomalies = [e for e in est.employees if e.overall_verdict == "ANOMALIE"]
        ok = [e for e in est.employees if e.overall_verdict in {"PARFAIT", "OK"}]
        lines.append(
            f"### Salariés — {len(ok)} OK / {len(anomalies)} anomalies / "
            f"{len(est.employees)} total"
        )
        lines.append("")
        for emp in est.employees:
            if emp.overall_verdict in {"PARFAIT", "OK"} and not emp.quarantine:
                continue
            lines.append(
                f"#### `{emp.employee_key}` — {emp.overall_verdict} "
                f"(match={emp.match_method}"
                f"{', quarantaine' if emp.quarantine else ''})"
            )
            lines.append("")
            lines.append("| Domaine | Champ | Tier | Réf | Act | Δ | Verdict |")
            lines.append("|---|---|---|---:|---:|---:|---|")
            for ln in emp.lines:
                if ln.verdict in {"PARFAIT", "OK"}:
                    continue
                lines.append(
                    f"| {ln.domain} | {ln.field} | {ln.tier} | {ln.ref} | {ln.act} | "
                    f"{ln.delta} | **{ln.verdict}** |"
                )
            lines.append("")

    return "\n".join(lines) + "\n"


def write_reports(
    report: DsnComparisonReport,
    *,
    json_path: str | None = None,
    md_path: str | None = None,
) -> Dict[str, str]:
    """Écrit les rapports sur disque (lecture/écriture locale uniquement)."""
    out: Dict[str, str] = {}
    if json_path:
        content = report_to_json(report)
        with open(json_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        out["json"] = json_path
    if md_path:
        content = report_to_markdown(report)
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        out["markdown"] = md_path
    return out
