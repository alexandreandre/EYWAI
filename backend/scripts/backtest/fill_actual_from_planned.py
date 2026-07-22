"""Remplit actual_hours.calendrier_reel (heures FAITES, affichées dans l'UI) en
recopiant les jours travaillés du calendrier PRÉVU, pour toutes les entreprises.

Sûr : ne remplit QUE là où calendrier_reel est vide (n'écrase jamais un vrai
pointage). Heures faites = prévu => la paie est INCHANGÉE (le moteur calcule la
même base).

Usage: python -m scripts.backtest.fill_actual_from_planned [--year 2026] [--apply]
"""
from __future__ import annotations
import argparse, copy
from collections import defaultdict

from app.core.database import get_supabase_admin_client


# Sources actual_hours écrites par nos propres scripts (ré-écrivables sans risque).
OWN_SOURCES = {"calendrier_prevu", "repli_prevu", "pointage_import_ia"}


def _planned_reel(planned: dict) -> list:
    """Heures prévues recopiées en 'faites', marquées `source_repli_planning` : le
    moteur les traite comme repli planning (couvre les jours, AUCUNE HS/HC/absence
    fictive) => paie strictement inchangée, mais l'UI affiche les heures."""
    cal = (planned or {}).get("calendrier_prevu") or []
    return [{"jour": j["jour"], "type": "travail",
             "heures_faites": float(j.get("heures_prevues") or 0),
             "source_repli_planning": True}
            for j in cal if j.get("type") == "travail" and (j.get("heures_prevues") or 0) > 0]


def run(year: int, apply: bool) -> None:
    admin = get_supabase_admin_client()
    comps = {c["id"]: c.get("company_name") or c["id"]
             for c in admin.table("companies").select("id,company_name").execute().data}
    emps = admin.table("employees").select("id,company_id").execute().data
    emp_comp = {e["id"]: e["company_id"] for e in emps}
    eids = [e["id"] for e in emps]

    stats = defaultdict(lambda: {"filled": 0, "already": 0, "no_planned": 0})
    for i in range(0, len(eids), 50):
        chunk = eids[i:i + 50]
        scheds = (admin.table("employee_schedules")
                  .select("id,employee_id,month,planned_calendar,actual_hours")
                  .in_("employee_id", chunk).eq("year", year).lte("month", 6).execute().data) or []
        for s in scheds:
            cid = emp_comp.get(s["employee_id"])
            cname = comps.get(cid, cid)
            ah = s.get("actual_hours") or {}
            existing = ah.get("calendrier_reel")
            already_flagged = existing and all(d.get("source_repli_planning") for d in existing)
            # On (ré)écrit si vide OU si c'est un de NOS remplissages (pour ajouter/garder
            # le flag). On ne touche JAMAIS un vrai pointage (source inconnue/badgeuse).
            src = ah.get("source")
            is_own = isinstance(src, str) and src in OWN_SOURCES
            if existing and (already_flagged or not is_own):
                stats[cname]["already"] += 1
                continue
            reel = _planned_reel(s.get("planned_calendar"))
            if not reel:
                stats[cname]["no_planned"] += 1
                continue
            if apply:
                new_ah = copy.deepcopy(ah)
                new_ah.update({"source": "calendrier_prevu", "year": year,
                               "month": s["month"], "calendrier_reel": reel})
                admin.table("employee_schedules").update({"actual_hours": new_ah}).eq("id", s["id"]).execute()
            stats[cname]["filled"] += 1

    print(f"\n=== {'APPLIQUÉ' if apply else 'DRY-RUN'} — {year} ===")
    tot = defaultdict(int)
    for cname in sorted(stats):
        st = stats[cname]
        print(f"  {cname[:32]:32} rempli={st['filled']:4}  déjà={st['already']:4}  sans_prévu={st['no_planned']:4}")
        for k, v in st.items():
            tot[k] += v
    print(f"  {'TOTAL':32} rempli={tot['filled']:4}  déjà={tot['already']:4}  sans_prévu={tot['no_planned']:4}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    run(a.year, a.apply)


if __name__ == "__main__":
    main()
