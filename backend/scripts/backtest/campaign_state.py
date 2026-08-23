"""État de campagne backtest : snapshot, journal, state.yaml."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from app.core.database import supabase
from app.modules.payroll.backtest.models import DiscrepancyReport, EmployeeConvergenceStatus, Verdict

#: Les rapports de campagne portent des NOMS de salariés, leurs SALAIRES et
#: leurs NIR. Le dépôt est PUBLIC : ils vivent sous `data/`, qui est
#: gitignoré, jamais sous `docs/`. Douze rapports avaient été committés
#: avant ce correctif (23/08/2026), dont sept NIR et quatorze montants
#: nominatifs — retirés du suivi, mais l'historique les conserve.
RACINE_RAPPORTS = Path(__file__).resolve().parents[3] / "data" / "_backtests"

#: Ancien emplacement, lu seulement pour retrouver une campagne existante.
DOCS_ROOT_LEGACY = Path(__file__).resolve().parents[3] / "docs" / "backtest"


def campaign_dir(company_name: str, year: int, month: int) -> Path:
    """Dossier de campagne, sous data/. Une campagne déjà commencée à
    l'ancien emplacement y est reprise plutôt que dédoublée."""
    slug = company_name.lower().replace(" ", "-")
    periode = f"{year}-{month:02d}"
    ancien = DOCS_ROOT_LEGACY / slug / periode
    if ancien.is_dir():
        return ancien
    return RACINE_RAPPORTS / slug / periode


class CampaignState:
    def __init__(self, company_name: str, year: int, month: int):
        self.company_name = company_name
        self.year = year
        self.month = month
        self.dir = campaign_dir(company_name, year, month)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.dir / "journal.jsonl"
        self.state_path = self.dir / "state.json"
        self.snapshot_path = self.dir / "snapshot.json"
        self.report_path = self.dir / "report.md"
        self.catalog_path = self.dir / "pattern_catalog.json"
        self.progress_path = self.dir / "progress.log"

    def progress(self, message: str) -> None:
        """Feedback visible sans validation — append horodaté."""
        line = f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {message}\n"
        print(message, flush=True)
        with self.progress_path.open("a", encoding="utf-8") as f:
            f.write(line)

    def log(self, entry: Dict[str, Any]) -> None:
        entry = {**entry, "ts": datetime.now(timezone.utc).isoformat()}
        with self.journal_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def load_state(self) -> Dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {
            "company": self.company_name,
            "year": self.year,
            "month": self.month,
            "iteration": 0,
            "employees": {},
            "patterns_applied": [],
            "quarantines": [],
        }

    def save_state(self, state: Dict[str, Any]) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def snapshot_payslips(self, employee_ids: List[str]) -> None:
        snapshot: Dict[str, Any] = {}
        for emp_id in employee_ids:
            res = (
                supabase.table("payslips")
                .select("id, payslip_data")
                .match(
                    {
                        "employee_id": emp_id,
                        "year": self.year,
                        "month": self.month,
                    }
                )
                .maybe_single()
                .execute()
            )
            if res and res.data:
                snapshot[emp_id] = res.data.get("payslip_data")
        self.snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
        self.log({"action": "snapshot", "count": len(snapshot)})

    def update_employee_status(
        self,
        state: Dict[str, Any],
        matricule: str,
        report: DiscrepancyReport,
        *,
        name: str = "",
    ) -> None:
        verdict_map = {
            Verdict.PARFAIT: EmployeeConvergenceStatus.PARFAIT.value,
            Verdict.OK: EmployeeConvergenceStatus.OK.value,
            Verdict.TOLERE: EmployeeConvergenceStatus.TOLERE.value,
            Verdict.KNOWN_GAP: EmployeeConvergenceStatus.OK.value,
            Verdict.QUARANTAINE: EmployeeConvergenceStatus.QUARANTAINE.value,
            Verdict.ANOMALIE: EmployeeConvergenceStatus.IN_PROGRESS.value,
        }
        employees = state.setdefault("employees", {})
        # Convergence pilotée par tier S (champs légaux) — tier A/B peut rester imparfait
        tier_s_ok = report.tier_s_max_delta <= 0.05
        if tier_s_ok and report.overall_verdict != Verdict.QUARANTAINE:
            status = EmployeeConvergenceStatus.OK.value
            if report.overall_verdict == Verdict.PARFAIT:
                status = EmployeeConvergenceStatus.PARFAIT.value
            elif report.overall_verdict == Verdict.TOLERE:
                status = EmployeeConvergenceStatus.TOLERE.value
        else:
            status = verdict_map.get(
                report.overall_verdict, EmployeeConvergenceStatus.IN_PROGRESS.value
            )
        if report.correction_attempts >= 3 and not tier_s_ok:
            status = EmployeeConvergenceStatus.QUARANTAINE.value
            quarantines = state.setdefault("quarantines", [])
            if not any(q.get("matricule") == matricule for q in quarantines):
                quarantines.append(
                    {
                        "matricule": matricule,
                        "name": name,
                        "tier_s_max_delta": report.tier_s_max_delta,
                        "attempts": report.correction_attempts,
                    }
                )
        employees[matricule] = {
            "status": status,
            "overall_verdict": report.overall_verdict.value,
            "tier_s_max_delta": report.tier_s_max_delta,
            "correction_attempts": report.correction_attempts,
            "anomaly_count": sum(
                1 for ln in report.lines if ln.verdict == Verdict.ANOMALIE
            ),
        }

    def count_converged(self, state: Dict[str, Any]) -> tuple[int, int]:
        employees = state.get("employees") or {}
        ok_statuses = {"PARFAIT", "OK", "TOLERE", "validated"}
        converged = sum(1 for e in employees.values() if e.get("status") in ok_statuses)
        return converged, len(employees)
