"""Importe les pointages manuscrits Colorplast -> actual_hours.calendrier_reel
(les « heures faites » du calendrier), via le pipeline IA d'EYWAI
(ai_fill.extract_timesheet, hybrid vision+OCR).

Chaque pointage = une semaine ISO (n° dans le nom de fichier). On ancre à la
date du lundi ISO, on mappe jour(1-7 relatif) -> date absolue via la période
détectée, puis on assigne chaque jour à SON mois réel (semaines à cheval gérées).

Usage:
  python -m scripts.backtest.pointage_import --dump           # extrait tout, dump JSON, n'écrit rien
  python -m scripts.backtest.pointage_import --apply --month 6  # persiste calendrier_reel du mois
"""
from __future__ import annotations
import argparse, glob, json, os, re
from pathlib import Path
from datetime import date, timedelta

os.environ.setdefault("TESSDATA_PREFIX", "/usr/local/share/tessdata")
from PIL import Image
Image.MAX_IMAGE_PIXELS = None

from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id
from app.modules.schedules.application import ai_fill
from app.modules.schedules.schemas.ai import RosterEmployee

REPO = Path(__file__).resolve().parents[3]
BUL = REPO / "Bulletins" / "BULLETIN COLORPLAST 01 02 03 04 05 06"
SC = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "74b8d7a4-40cc-4555-b2ae-3c2d43ad6c41/scratchpad")
CACHE = SC / "pointage_extract_colorplast.json"

POINTAGE_DIRS = [
    BUL / "01", BUL / "02", BUL / "03", BUL / "04", BUL / "06",
    REPO / "Config" / "Colorplast" / "Pointages",
]
WEEK_RE = re.compile(r"(?:S|SEMAINE)\s*0*(\d{1,2})", re.IGNORECASE)


def _week_files() -> dict[int, str]:
    """{n° semaine ISO: chemin PDF}. Dédoublonne par n° de semaine."""
    out = {}
    for d in POINTAGE_DIRS:
        for f in glob.glob(str(d / "*.pdf")):
            name = Path(f).name
            if "POINTAGE" not in name.upper() and "SEMAINE" not in name.upper():
                continue
            m = WEEK_RE.search(name)
            if m:
                wk = int(m.group(1))
                out.setdefault(wk, f)
    return dict(sorted(out.items()))


def _roster(admin, cid):
    emps = admin.table("employees").select("id,first_name,last_name").eq("company_id", cid).execute().data
    roster = [RosterEmployee(id=e["id"], first_name=e.get("first_name") or "",
                             last_name=e.get("last_name") or "") for e in emps]
    return roster, {e["id"]: e.get("last_name") for e in emps}


def extract_all(year: int = 2026) -> dict:
    """Extrait toutes les semaines -> {matricule: {"YYYY-MM": {jour: heures}}}."""
    admin = get_supabase_admin_client()
    cid = resolve_company_id("Colorplast")
    roster, id2mat = _roster(admin, cid)
    weeks = _week_files()
    print(f"{len(weeks)} semaines: {sorted(weeks)}", flush=True)
    result: dict = {}
    for wk, f in weeks.items():
        try:
            anchor = date.fromisocalendar(year, wk, 1)
        except ValueError:
            print(f"  S{wk}: n° hors année, skip"); continue
        content = Path(f).read_bytes()
        try:
            resp = ai_fill.extract_timesheet(
                year=anchor.year, month=anchor.month, file_content=content,
                filename=Path(f).name, roster=roster, single_employee=False,
                document_scope="weekly", week_anchor_date=anchor, company_id=cid, user_id=None)
            d = resp.model_dump()
        except Exception as e:
            print(f"  S{wk} [{Path(f).name}] ERREUR: {str(e)[:60]}", flush=True); continue
        ps = d.get("detected_period_start")
        if isinstance(ps, date):
            start = ps
        elif isinstance(ps, str) and ps:
            start = date.fromisoformat(ps[:10])
        else:
            start = anchor
        n = 0
        for emp in d.get("employees") or []:
            mat = id2mat.get(emp.get("employee_id"))
            if not mat:
                continue
            for day in emp.get("days") or []:
                j = day.get("jour"); h = day.get("heures")
                if not j or h is None:
                    continue
                dt = start + timedelta(days=int(j) - 1)
                key = f"{dt.year}-{dt.month:02d}"
                result.setdefault(mat, {}).setdefault(key, {})[dt.day] = float(h)
                n += 1
        print(f"  S{wk} [{Path(f).name}] {start}..: {n} jours", flush=True)
        CACHE.write_text(json.dumps(result, ensure_ascii=False, indent=1))  # cache incrémental
    CACHE.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(f"\ncache -> {CACHE}", flush=True)
    return result


def _dump(result: dict, year: int):
    print("\n=== récap heures faites par salarié/mois ===")
    for mat in sorted(result):
        for key in sorted(result[mat]):
            if not key.startswith(str(year)):
                continue
            days = result[mat][key]
            print(f"  {mat:12} {key}: {len(days)}j {sum(days.values()):.1f}h  {dict(sorted(days.items()))}")


def apply_month(result: dict, year: int, month: int):
    admin = get_supabase_admin_client()
    cid = resolve_company_id("Colorplast")
    emps = admin.table("employees").select("id,last_name").eq("company_id", cid).execute().data
    mat2id = {e.get("last_name"): e["id"] for e in emps}
    key = f"{year}-{month:02d}"
    written = 0
    for mat, months in result.items():
        days = months.get(key)
        eid = mat2id.get(mat)
        if not days or not eid:
            continue
        reel = [{"jour": j, "type": "travail", "heures_faites": round(h, 2)}
                for j, h in sorted(days.items())]
        sch = (admin.table("employee_schedules").select("id,actual_hours")
               .match({"employee_id": eid, "year": year, "month": month}).maybe_single().execute())
        ah = {"source": "pointage_import_ia", "year": year, "month": month, "calendrier_reel": reel}
        if sch and sch.data:
            admin.table("employee_schedules").update({"actual_hours": ah}).eq("id", sch.data["id"]).execute()
        else:
            admin.table("employee_schedules").insert(
                {"employee_id": eid, "year": year, "month": month, "actual_hours": ah}).execute()
        written += 1
    print(f"APPLY {key}: calendrier_reel écrit pour {written} salariés")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int, default=None)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--from-cache", action="store_true")
    a = ap.parse_args()
    if a.from_cache and CACHE.exists():
        result = json.loads(CACHE.read_text())
    else:
        result = extract_all(a.year)
    _dump(result, a.year)
    if a.apply:
        months = [a.month] if a.month else range(1, 7)
        for m in months:
            apply_month(result, a.year, m)


if __name__ == "__main__":
    main()
