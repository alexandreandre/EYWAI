"""Déclare les arrêts LEWIS (comme la RH depuis les arrêts de travail) : marque les
jours calendrier en arret_maladie/arret_at avec le VRAI début (date_debut_arret_reel)
+ subrogation, puis régénère. Le moteur calcule maintien (épuisement) + IJSS.

Les DATES d'arrêt sont des faits métier (arrêt de travail), pas un input DSN de
paie : on les lit dans la DSN comme référence de ce que la RH déclarerait.

Usage: python -m scripts.backtest.lewis_arret_declare [--apply] [MATRICULE ...]
"""
from __future__ import annotations
import argparse, calendar as _cal, copy, re, sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import scripts.backtest.lewis_reconcile as _R  # stubs weasyprint/storage
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.employee_matching import match_employees
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds
from app.modules.payroll.documents.payslip_generator import process_payslip_generation

REPO = Path(__file__).resolve().parents[3]
DSN = {m: REPO / "Config/Lewis/DSN" / f for m, f in {
    1: "LEWIS_0126_000001 (1).dsn", 2: "LEWIS_0226_000001.dsn",
    3: "LEWIS_0326_000001.dsn", 4: "LEWIS_0426_000001.dsn",
    5: "LEWIS_0526_000001.dsn"}.items()}
ARRET_TYPE = {"01": "maladie_simple", "05": "accident_travail", "06": "accident_travail"}


def _d(s):
    s = (s or "").strip()
    return date(int(s[4:8]), int(s[2:4]), int(s[0:2])) if re.fullmatch(r"\d{8}", s) else None


def parse_arrets():
    """{matricule: {mois: {motif, debut_reel(date), fin(date)}}}"""
    out = {}
    for m, f in DSN.items():
        lines = f.read_text(encoding="latin-1").splitlines()
        idx = [i for i, l in enumerate(lines) if l.startswith("S21.G00.30.002")]
        for k, s in enumerate(idx):
            e = idx[k + 1] if k + 1 < len(idx) else len(lines)
            b = lines[s:e]; nom = b[0].split(",")[1].strip("'")
            cur = None; arrs = []
            for l in b:
                mo = re.match(r"S21\.G00\.60\.(\d+),'([^']*)'", l)
                if mo:
                    if mo.group(1) == "001":
                        if cur:
                            arrs.append(cur)
                        cur = {}
                    if cur is not None:
                        cur[mo.group(1)] = mo.group(2)
            if cur:
                arrs.append(cur)
            for a in arrs:
                dernier = _d(a.get("002")); fin = _d(a.get("003"))
                reprise = _d(a.get("010"))
                if fin is None and reprise:
                    fin = reprise - timedelta(days=1)
                if dernier is None or fin is None:
                    continue
                out.setdefault(nom, {})[m] = {
                    "motif": a.get("001"),
                    "debut_reel": (dernier + timedelta(days=1)),
                    "fin": fin,
                }
    return out


def declare(company="LEWIS", year=2026, apply=False, only=None):
    admin = get_supabase_admin_client()
    cid = resolve_company_id(company)
    emps = {e["last_name"]: e["id"] for e in admin.table("employees")
            .select("id,last_name").eq("company_id", cid).execute().data}
    arrets = parse_arrets()
    for mat in sorted(arrets):
        if only and mat not in only:
            continue
        eid = emps.get(mat)
        if not eid:
            print(f"[{mat}] introuvable"); continue
        # Vrai début = le plus ancien sur tous les mois (arrêt continu multi-mois).
        debut_reel_emp = min(info["debut_reel"] for info in arrets[mat].values())
        for m, info in sorted(arrets[mat].items()):
            debut_reel = debut_reel_emp; fin = info["fin"]
            # Subrogation active tant que le maintien n'est vraisemblablement pas
            # épuisé (~100 j de maintien légal max). Au-delà : IJSS directe (pas de
            # subrogation au bulletin). Affiné par itération sur les non-convergés.
            jours_ecoules = (date(year, m, 1) - debut_reel).days
            subrog = jours_ecoules <= 100
            arret_type = ARRET_TYPE.get(info["motif"], "maladie_simple")
            dim = _cal.monthrange(year, m)[1]
            d0 = max(debut_reel, date(year, m, 1))
            d1 = min(fin, date(year, m, dim))
            jours = {d.day for d in (d0 + timedelta(days=i) for i in range((d1 - d0).days + 1))}
            s = (admin.table("employee_schedules").select("id,planned_calendar")
                 .match({"employee_id": eid, "year": year, "month": m}).maybe_single().execute())
            if not (s and s.data):
                print(f"[{mat}] m{m}: pas de schedule"); continue
            pc = copy.deepcopy(s.data.get("planned_calendar") or {})
            cal = pc.get("calendrier_prevu") or []
            n = 0
            for j in cal:
                if j.get("jour") in jours and j.get("type") == "travail":
                    j["type"] = "arret_maladie"; j["arret_type"] = arret_type
                    j["date_debut_arret_reel"] = debut_reel.isoformat()
                    j["subrogation_active"] = subrog
                    n += 1
            pc["calendrier_prevu"] = cal
            print(f"[{mat}] m{m}: {n}j arrêt ({arret_type}, début {debut_reel}, subrog={subrog})")
            if apply:
                admin.table("employee_schedules").update(
                    {"planned_calendar": pc, "actual_hours": {}}).eq("id", s.data["id"]).execute()
                try:
                    process_payslip_generation(eid, year, m)
                except Exception as ex:
                    print(f"   gen err {str(ex)[:50]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("mats", nargs="*")
    a = ap.parse_args()
    declare(apply=a.apply, only=set(a.mats) or None)


if __name__ == "__main__":
    main()
