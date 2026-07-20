"""Backup CIBLÉ Cartol (Supabase cloud, pas de dump fichier possible).

Snapshot JSON de: employees (config complète), employee_schedules (jan-juin),
monthly_inputs (jan-juin) pour TOUS les salariés Cartol. Sert de filet de
sécurité avant toute mutation. Restaure avec --restore.

Usage:
  .venv/bin/python -m scripts.backtest.cartol_backup            # backup
  .venv/bin/python -m scripts.backtest.cartol_backup --restore  # restore
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id

COMPANY = "Cartol"
YEAR = 2026
OUT = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad/cartol_db_backup.json")


def backup():
    admin = get_supabase_admin_client()
    cid = resolve_company_id(COMPANY)
    emps = admin.table("employees").select("*").eq("company_id", cid).execute().data
    eids = [e["id"] for e in emps]
    scheds, inputs = [], []
    # chunk to avoid huge IN clauses
    for i in range(0, len(eids), 40):
        chunk = eids[i:i + 40]
        scheds += (admin.table("employee_schedules").select("*")
                   .in_("employee_id", chunk).eq("year", YEAR).execute().data) or []
        inputs += (admin.table("monthly_inputs").select("*")
                   .in_("employee_id", chunk).eq("year", YEAR).execute().data) or []
    data = {"company_id": cid, "employees": emps, "schedules": scheds, "inputs": inputs}
    OUT.write_text(json.dumps(data, ensure_ascii=False, default=str))
    print(f"BACKUP OK -> {OUT}")
    print(f"  employees={len(emps)} schedules={len(scheds)} inputs={len(inputs)}")


def restore():
    admin = get_supabase_admin_client()
    data = json.loads(OUT.read_text())
    cid = data["company_id"]
    # employees: update config fields only (never delete employees)
    for e in data["employees"]:
        admin.table("employees").update({
            "salaire_de_base": e.get("salaire_de_base"),
            "seniority_reference_date": e.get("seniority_reference_date"),
            "specificites_paie": e.get("specificites_paie"),
            "is_forfait_jour": e.get("is_forfait_jour"),
        }).eq("id", e["id"]).execute()
    # schedules: restore planned_calendar + actual_hours
    for s in data["schedules"]:
        admin.table("employee_schedules").update({
            "planned_calendar": s.get("planned_calendar"),
            "actual_hours": s.get("actual_hours"),
        }).eq("id", s["id"]).execute()
    # monthly_inputs: delete all 2026 then re-insert snapshot
    eids = [e["id"] for e in data["employees"]]
    for i in range(0, len(eids), 40):
        admin.table("monthly_inputs").delete().in_("employee_id", eids[i:i + 40]).eq("year", YEAR).execute()
    cols = ("employee_id", "company_id", "year", "month", "name", "description", "amount",
            "is_socially_taxed", "is_taxable", "payroll_quantity", "catalog_prime_id",
            "export_code", "bonus_type_id", "participation_campaign_id", "participation_bulletin_id")
    for r in data["inputs"]:
        admin.table("monthly_inputs").insert({k: r.get(k) for k in cols if k in r}).execute()
    print(f"RESTORE OK: {len(data['employees'])} emps, {len(data['schedules'])} scheds, {len(data['inputs'])} inputs")


if __name__ == "__main__":
    (restore if "--restore" in sys.argv else backup)()
