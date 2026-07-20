"""Reconcile data-driven Cartol depuis l'extract réel, revert-si-pire, 1 salarié/fois.

Auto-dérive le patch mensuel depuis scratchpad/cartol_extract_<MM>.json (ancre
documentaire réelle) :
  - seniority_reference_date = date Ancienneté du bulletin (prime anc via moteur)
  - prévoyance EP1/EP3 (taux réels du bulletin, base brut_plafonne)
  - participation numéraire (+ acompte participation net-only)
  - CP (calendrier), JF non payé (absences), HS 25/50 conjoncturelles
  - note de frais (net-only, reste dans MNS)

Applique, régénère, compare : GARDE si tierS baisse, sinon REVERT intégral.

Usage: .venv/bin/python -m scripts.backtest.cartol_reconcile --month 5 --emp BERTAUD [...]
       (sans --emp : tous les matchés, triés par écart croissant via measure JSON)
"""
from __future__ import annotations
import argparse, calendar as _cal, copy, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

# Stub PDF/storage (comme measure_par.py) : ~10x plus rapide sur 86 salariés.
import weasyprint as _wp


def _pdf_stub(self, target=None, *a, **k):
    if target is None:
        return b"%PDF-1.4\n%stub\n"
    if hasattr(target, "write"):
        target.write(b"%PDF-1.4\n%stub\n"); return None
    open(target, "wb").write(b"%PDF-1.4\n%stub\n"); return None


_wp.HTML.write_pdf = _pdf_stub
import app.modules.payroll.documents.payslip_generator as _pg


class _FakeBucket:
    def upload(self, *a, **k):
        return None

    def create_signed_url(self, *a, **k):
        return {"signedURL": "stub"}


try:
    _pg.supabase.storage.from_ = lambda *a, **k: _FakeBucket()
except Exception:
    pass
import app.modules.employee_loans.application.payroll_integration as _pi

_pi.enrich_payslip_after_upsert = lambda data, *a, **k: data

COMPANY = "Cartol"
MARKER = "BACKTEST_AUTO_CARTOL"
SC = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad")


def tier_s(match, year, month):
    for attempt in range(3):  # retry sur erreur SSL transitoire (upload storage)
        try:
            _generate_payslip(match, year, month)
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"    (retry gen {match.matricule}: {str(e)[:40]})")
    for r in compare_matches([match], year, month, thresholds=default_thresholds(),
                             systemic_deltas={}, correction_attempts={}):
        return r.tier_s_max_delta
    return float("inf")


def _snapshot(admin, eid, year, month):
    emp = admin.table("employees").select(
        "salaire_de_base,seniority_reference_date,specificites_paie,is_forfait_jour"
    ).eq("id", eid).single().execute().data
    sched = (admin.table("employee_schedules").select("id,planned_calendar,actual_hours")
             .match({"employee_id": eid, "year": year, "month": month}).maybe_single().execute())
    inputs = (admin.table("monthly_inputs").select("*")
              .match({"employee_id": eid, "year": year, "month": month}).execute().data) or []
    return {"emp": copy.deepcopy(emp),
            "sched": copy.deepcopy(sched.data if sched and sched.data else None),
            "inputs": copy.deepcopy(inputs)}


def _restore(admin, eid, cid, year, month, snap):
    admin.table("employees").update({
        "salaire_de_base": snap["emp"].get("salaire_de_base"),
        "seniority_reference_date": snap["emp"].get("seniority_reference_date"),
        "specificites_paie": snap["emp"].get("specificites_paie"),
    }).eq("id", eid).execute()
    if snap["sched"]:
        admin.table("employee_schedules").update({
            "planned_calendar": snap["sched"].get("planned_calendar"),
            "actual_hours": snap["sched"].get("actual_hours"),
        }).eq("id", snap["sched"]["id"]).execute()
    admin.table("monthly_inputs").delete().match(
        {"employee_id": eid, "year": year, "month": month}).execute()
    cols = ("name", "description", "amount", "is_socially_taxed", "is_taxable",
            "payroll_quantity", "catalog_prime_id", "export_code", "bonus_type_id",
            "participation_campaign_id", "participation_bulletin_id")
    for row in snap["inputs"]:
        payload = {k: row.get(k) for k in cols if k in row}
        payload.update({"employee_id": eid, "company_id": cid, "year": year, "month": month})
        admin.table("monthly_inputs").insert(payload).execute()


def _apply(admin, emp_row, cid, year, month, ext, opts):
    eid = emp_row["id"]
    sp = copy.deepcopy(emp_row.get("specificites_paie") or {})
    sp_dirty = False
    # 1. prévoyance depuis taux réel du bulletin
    if opts["prevoyance"] and ext.get("prev"):
        rate = round((ext["prev"]["rate"] or 0) / 100.0, 6)
        sp["prevoyance"] = {"adhesion": True, "lignes_specifiques": [
            {"id": "prevoyance_dsn", "base": "brut_plafonne",
             "libelle": "Prévoyance Groupama (bulletin)",
             "salarial": rate, "patronal": rate, "forfait_social": 0.08}]}
        sp_dirty = True
    # 2. mutuelle : les types company_mutuelle_types Cartol sont TOUS importés
    #    100% salarial / 0% patronal (bug #11/#20). Override par salarié via
    #    lignes_specifiques (sal/pat réels du bulletin), sans éditer le type
    #    partagé. Cartol NE réintègre PAS la part patronale au net imposable.
    if opts["mutuelle"]:
        if ext.get("mut"):
            mut = ext["mut"]
            sp["mutuelle"] = {"adhesion": True, "part_patronale_reintegree_impot": False,
                              "mutuelle_type_ids": [],
                              "lignes_specifiques": [{
                                  "libelle": "Mutuelle " + (mut.get("label") or "").title(),
                                  "montant_salarial": float(mut["sal"]),
                                  "montant_patronal": float(mut["pat"]),
                                  "part_patronale_soumise_a_csg": True}]}
        else:
            sp["mutuelle"] = {"adhesion": False}
        sp_dirty = True
    # 3. prime ancienneté : Cartol = montant GELÉ (métallurgie 2024), pas la formule
    #    moteur. Désactive le calcul moteur -> on injecte le montant réel exact.
    if opts["prime_anc"] and ext.get("prime_anc"):
        pa = dict(sp.get("prime_anciennete") or {})
        pa["incluse_dans_salaire_base"] = True
        sp["prime_anciennete"] = pa
        sp_dirty = True
    if sp_dirty:
        admin.table("employees").update({"specificites_paie": sp}).eq("id", eid).execute()
    # 4. modulation annuelle : vider actual_hours (badgeuse) -> supprime les HS
    #    hebdo fantômes. Sous annualisation les heures > 35h/sem sont mises en
    #    réserve dans le compteur modulation, PAS payées en HS. Les vraies HS
    #    payées sont réinjectées depuis le bulletin réel (hs25_h/hs50_h).
    if opts["calendar"]:
        _clear_actual(admin, eid, year, month)
        _set_calendar(admin, eid, year, month, ext.get("cp_days") or [],
                      ext.get("jf_non_paye_days") or [])
    # 4. monthly_inputs
    admin.table("monthly_inputs").delete().match(
        {"employee_id": eid, "year": year, "month": month}).like("description", f"%{MARKER}%").execute()
    inputs = []
    if opts["prime_anc"] and ext.get("prime_anc"):
        inputs.append(("Prime d'ancienneté", float(ext["prime_anc"]), True, True, None))
    if opts["participation"] and ext.get("participation"):
        inputs.append(("Participation 2025", float(ext["participation"]), False, True, None))
    if opts["participation"] and ext.get("participation_pee"):
        inputs.append(("Participation 2025 PEE", float(ext["participation_pee"]), False, False, None))
    if opts["participation"] and ext.get("acompte_participation"):
        # Acompte déjà versé = retenue NET-ONLY (label sans "participation" -> canal acompte)
        inputs.append(("Acompte versé", -abs(float(ext["acompte_participation"])), False, False, None))
    if opts["hs"] and ext.get("hs25_h"):
        inputs.append(("Heures supplementaires conjoncturelles", 0.0, True, True, round(ext["hs25_h"], 2)))
    if opts["hs"] and ext.get("hs50_h"):
        inputs.append(("Heures supplementaires conjoncturelles 50%", 0.0, True, True, round(ext["hs50_h"], 2)))
    if opts["notefrais"] and ext.get("note_frais"):
        inputs.append(("Remboursement note de frais", float(ext["note_frais"]), False, False, None))
    for name, amt, taxed, taxable, qty in inputs:
        row = {"employee_id": eid, "company_id": cid, "year": year, "month": month,
               "name": name, "description": f"Backtest Cartol {month:02d}/{year} {MARKER}",
               "amount": amt, "is_socially_taxed": taxed, "is_taxable": taxable}
        if qty is not None:
            row["payroll_quantity"] = qty
        admin.table("monthly_inputs").insert(row).execute()
    return [i[0] for i in inputs]


def _clear_actual(admin, eid, year, month):
    sch = (admin.table("employee_schedules").select("id,actual_hours")
           .match({"employee_id": eid, "year": year, "month": month}).maybe_single().execute())
    if not sch or not sch.data:
        return
    ah = sch.data.get("actual_hours") or {}
    if not ah.get("calendrier_reel"):
        return
    ah = copy.deepcopy(ah); ah["calendrier_reel"] = []
    admin.table("employee_schedules").update({"actual_hours": ah}).eq("id", sch.data["id"]).execute()


def _set_calendar(admin, eid, year, month, cp_days, jf_days):
    sch = (admin.table("employee_schedules").select("id,planned_calendar")
           .match({"employee_id": eid, "year": year, "month": month}).maybe_single().execute())
    if not sch or not sch.data:
        return
    dim = _cal.monthrange(year, month)[1]
    planned = copy.deepcopy(sch.data.get("planned_calendar") or {})
    cal = [j for j in planned.get("calendrier_prevu", []) if 1 <= j.get("jour", 0) <= dim]
    by_day = {j.get("jour"): j for j in cal}
    for d in [x for x in cp_days if 1 <= x <= dim]:
        j = by_day.get(d)
        if j is None:
            cal.append({"jour": d, "type": "conges_payes", "manuel": True, "heures_prevues": 7.0})
        elif j.get("type") == "travail":
            j["type"] = "conges_payes"; j["manuel"] = True
    for d in [x for x in jf_days if 1 <= x <= dim]:
        j = by_day.get(d)
        if j is None:
            cal.append({"jour": d, "type": "absence_non_remuneree", "manuel": True, "heures_prevues": 7.0})
        elif j.get("type") == "travail":
            j["type"] = "absence_non_remuneree"; j["manuel"] = True
    planned["calendrier_prevu"] = sorted(cal, key=lambda x: x["jour"])
    admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sch.data["id"]).execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, default=5)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--emp", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    for o in ["prime_anc", "prevoyance", "mutuelle", "calendar", "participation", "hs", "notefrais"]:
        ap.add_argument(f"--no-{o}", dest=o, action="store_false")
    a = ap.parse_args()
    opts = {o: getattr(a, o) for o in ["prime_anc", "prevoyance", "mutuelle", "calendar", "participation", "hs", "notefrais"]}
    admin = get_supabase_admin_client()
    pdf = resolve_bulletin_pdf(COMPANY, a.year, a.month)
    refs = load_reference_bulletins(COMPANY, a.year, a.month, pdf_path=pdf)
    cid = resolve_company_id(COMPANY)
    matched = {m.matricule: m for m in match_employees(cid, refs).matched}
    ext_all = json.loads((SC / f"cartol_extract_{a.month:02d}.json").read_text())
    if a.emp:
        order = [m for m in a.emp if m in matched]
    else:
        meas_path = SC / f"cartol_measure_{a.month:02d}.json"
        meas = json.loads(meas_path.read_text()) if meas_path.exists() else {}
        if len(meas) >= len(matched) - 2:  # measure JSON complet
            order = [m for m, _ in sorted(meas.items(), key=lambda x: x[1]["tierS"]) if m in matched]
            order = [m for m in order if meas[m]["tierS"] > 0.05]
        else:  # fallback : tous les matchés, ordre alpha
            order = sorted(matched.keys())
    if a.limit:
        order = order[:a.limit]
    results = []
    for mat in order:
        m = matched[mat]
        ext = ext_all.get(mat, {})
        try:
            emp_row = admin.table("employees").select("id,specificites_paie,salaire_de_base").eq("id", m.employee_id).single().execute().data
            before = tier_s(m, a.year, a.month)
            snap = _snapshot(admin, m.employee_id, a.year, a.month)
            names = _apply(admin, emp_row, cid, a.year, a.month, ext, opts)
            after = tier_s(m, a.year, a.month)
            keep = a.force or after < before - 0.01
            if keep:
                print(f"[{mat:12s}] {before:8.2f} -> {after:8.2f} GARDÉ  ({','.join(names)})")
            else:
                _restore(admin, m.employee_id, cid, a.year, a.month, snap)
                rev = tier_s(m, a.year, a.month)
                print(f"[{mat:12s}] {before:8.2f} -> {after:8.2f} REVERT->{rev:8.2f}")
            results.append((mat, before, after, keep))
        except Exception as e:
            print(f"[{mat:12s}] ERREUR: {str(e)[:60]} -- skip")
            results.append((mat, None, None, False))
    conv = sum(1 for _, _, af, k in results if k and af is not None and af <= 0.05)
    print(f"\n=== {len(results)} traités, {conv} convergés (<=0.05) ===")


if __name__ == "__main__":
    main()
