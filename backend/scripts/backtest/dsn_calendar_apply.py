"""Écriture (idempotente) des données DSN dans la DB : HS -> monthly_inputs,
absences -> planned_calendar. Marqueur DSN_LOADER. Ne touche pas primes/CP.

Utilisé par dsn_calendar_loader.py --apply.
"""
from __future__ import annotations
import copy

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id

MARKER = "DSN_LOADER"
HS_NAME_25 = "Heures supplementaires conjoncturelles"
HS_NAME_50 = "Heures supplementaires conjoncturelles 50%"
ABS_TYPES = {"absence_non_remuneree", "arret_maladie", "arret_maternite",
             "arret_paternite", "arret_at", "absence"}


def _standard_heures(cal: list) -> float:
    for j in cal:
        if j.get("type") == "travail" and j.get("heures_prevues"):
            return float(j["heures_prevues"])
    return 7.8


def _reset_dsn_calendar(cal: list, std: float) -> list:
    """Remet les jours d'absence marqués DSN_LOADER en travail. Laisse CP/ferie/repos
    et les absences non marquées DSN_LOADER (ex. posées manuellement ailleurs)."""
    for j in cal:
        if j.get("dsn_loader") and j.get("type") in ABS_TYPES:
            j["type"] = "travail"
            j["heures_prevues"] = std
            j.pop("dsn_loader", None)
            j["manuel"] = False
    return cal


def _place_absence_hours(cal, by_day, year, month, hours, std, abs_type, dim):
    """Pose `hours` d'absence non-datée sur des jours ouvrés (fin de mois vers début),
    net-neutre au jour près. Remplit chaque jour jusqu'à std."""
    remaining = round(hours, 2)
    for d in range(dim, 0, -1):
        if remaining <= 0.01:
            break
        j = by_day.get(d)
        if j is None or j.get("type") != "travail":
            continue
        h = min(remaining, std)
        j["type"] = abs_type
        j["heures_prevues"] = round(h, 2)
        j["manuel"] = True
        j["dsn_loader"] = True
        remaining = round(remaining - h, 2)
    return remaining


def _place_absence_days(cal, by_day, days, std, abs_type, dim):
    """Pose une absence datée (arrêt) sur des jours précis (jours ouvrés du mois)."""
    for d in days:
        if not 1 <= d <= dim:
            continue
        j = by_day.get(d)
        if j is None:
            j = {"jour": d}
            cal.append(j); by_day[d] = j
        # ne pas écraser un repos/ferie (l'arrêt sur un jour non ouvré n'a pas d'effet paie)
        if j.get("type") in ("repos", "ferie"):
            continue
        j["type"] = abs_type
        j["heures_prevues"] = std
        j["manuel"] = True
        j["dsn_loader"] = True


def apply_records(company: str, year: int, month: int, recs: dict) -> None:
    import calendar as _cal
    admin = get_supabase_admin_client()
    cid = resolve_company_id(company)
    dim = _cal.monthrange(year, month)[1]
    emps = admin.table("employees").select("id,matricule").eq("company_id", cid).execute().data
    mat2id = {e["matricule"]: e["id"] for e in emps}

    for mat, rec in sorted(recs.items()):
        eid = mat2id.get(mat)
        if not eid:
            print(f"[{mat}] introuvable en DB"); continue

        # 1. HS : purge des anciennes lignes HS (tout marqueur) puis réinsertion DSN
        admin.table("monthly_inputs").delete().match(
            {"employee_id": eid, "year": year, "month": month}
        ).like("name", "Heures supplementaires%").execute()
        for name, qty in ((HS_NAME_25, rec["h25"]), (HS_NAME_50, rec["h50"])):
            if qty and qty > 0:
                admin.table("monthly_inputs").insert({
                    "employee_id": eid, "company_id": cid, "year": year, "month": month,
                    "name": name, "amount": 0.0, "payroll_quantity": round(qty, 2),
                    "is_socially_taxed": True, "is_taxable": True,
                    "description": f"DSN {month:02d}/{year} {MARKER}",
                }).execute()

        # 2. calendrier : reset des absences DSN_LOADER, puis pose des absences DSN
        sch = (admin.table("employee_schedules").select("id,planned_calendar")
               .match({"employee_id": eid, "year": year, "month": month})
               .maybe_single().execute())
        if not sch or not sch.data:
            print(f"[{mat}] pas de schedule {month:02d}"); continue
        planned = copy.deepcopy(sch.data.get("planned_calendar") or {})
        cal = planned.get("calendrier_prevu", [])
        std = _standard_heures(cal)
        cal = _reset_dsn_calendar(cal, std)
        by_day = {j.get("jour"): j for j in cal}

        placed = []
        # arrêts datés
        arret_days_all = set()
        for typ, lib, days, motif in rec["arrets"]:
            _place_absence_days(cal, by_day, days, std, typ, dim)
            arret_days_all |= set(days)
            placed.append(f"{typ} j{days}")
        # absences non datées (53 nat02) NON déjà couvertes par un arrêt
        abs_h = rec.get("abs_hours_53", 0.0)
        if abs_h > 0.01 and not arret_days_all:
            left = _place_absence_hours(cal, by_day, year, month, abs_h, std,
                                        "absence_non_remuneree", dim)
            placed.append(f"abs {abs_h:.1f}h (reste {left:.1f})")

        planned["calendrier_prevu"] = sorted(cal, key=lambda x: x.get("jour", 0))
        admin.table("employee_schedules").update(
            {"planned_calendar": planned}).eq("id", sch.data["id"]).execute()
        print(f"[{mat}] HS25={rec['h25']:.2f} HS50={rec['h50']:.2f} | "
              f"{'; '.join(placed) if placed else 'pas d absence'}")
