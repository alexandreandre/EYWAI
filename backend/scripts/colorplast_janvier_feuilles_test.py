"""Rejeu de janvier 2026 de Colorplast sur le TEST à partir des feuilles de
pointage, en bac à sable dans le temps : l'état des fiches est relevé avant,
l'état de janvier est posé, les bulletins sont générés et comparés à Quadra,
puis les fiches sont remises comme elles étaient. Les mois suivants ne sont
pas touchés (juillet reste celui que Gaëlle ouvre le 15/09).

Heures lues sur `data/colorplast/pointages/2026-01/` (S02 à S05), avec la
règle de Gaëlle annotée sur la feuille S03 : heures = fin − début − 0,5 h de
pause quand la journée dépasse 6 h. Prénoms → salariés : Marion = Gautheron,
Michel = Bugny, Anthony = Espinosa, Léo = Cotte. Girerd (cadre) n'a pas de
feuille : mois sans pointage, planning repris tel quel.

Ce qui vient des feuilles et non du setup du backtest : les absences
(Gautheron 13 et 14/01, Cotte 21/01) et les heures sup (Bugny, Espinosa).
Le setup pose le reste (salaire de janvier, primes, acompte, mutuelle non
réintégrée comme chez Quadra, congé du 2/01). Le congé de Gautheron est posé
le jeudi 22 comme sur la feuille (Quadra l'a daté du 23).

Fenêtre des variables attendue : 22/12/2025 → 25/01/2026 ; la semaine S05
(26 → 30/01) est celle de février.

Attendus Quadra (brut) : Bugny 3 023,40 ; Cotte 2 351,89 ; Espinosa 3 046,68 ;
Gautheron 2 252,28 ; Girerd 3 799,06. HS Quadra : Bugny 12 h à 25 % + 8,5 h à
50 % ; Espinosa 12 + 4. Absences Quadra : Gautheron 13/01 2,5 h, 14/01 8,5 h ;
Cotte 21/01 3,5 h.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import supabase  # noqa: E402
from app.modules.payslips.application.commands import generate_payslip  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
)
from scripts.backtest.colorplast_setup import apply_month  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR, MONTH = 2026, 1
SALARIES = ("BUGNY", "COTTE", "ESPINOSA", "GAUTHERON", "GIRERD")

#: Heures nettes par jour lues sur les feuilles (jour du mois → heures).
#: Un jour absent du dictionnaire = pas de pointage (neutre).
FEUILLES = {
    "GAUTHERON": {
        5: 8.5, 6: 8.5, 7: 8.5, 8: 8.5, 9: 5.0,        # S02 : 39
        12: 8.5, 13: 6.0, 14: 0.0, 15: 8.5, 16: 5.0,    # S03 : 28 (6h–12h mardi, absente mercredi)
        19: 8.5, 20: 8.5, 21: 8.5, 23: 5.0,             # S04 : congé jeudi 22, vendredi travaillé
        # S05 : feuille vide, pas de pointage
    },
    "BUGNY": {
        5: 10.5, 6: 11.0, 7: 9.5, 8: 9.5, 9: 5.0,        # S02 : 45,5
        12: 9.5, 13: 9.0, 14: 9.5, 15: 10.0, 16: 5.0,    # S03 : 43
        19: 10.0, 20: 10.0, 21: 10.0, 22: 10.5, 23: 9.0, # S04 : 49,5
        26: 10.0, 27: 10.0, 28: 10.0, 29: 10.5, 30: 5.0, # S05 : 45,5 (février)
    },
    "ESPINOSA": {
        5: 9.5, 6: 9.5, 7: 9.5, 8: 9.5, 9: 6.0,          # S02 : 44
        12: 9.5, 13: 8.5, 14: 10.0, 15: 10.0, 16: 6.0,   # S03 : 44
        19: 9.5, 20: 9.5, 21: 9.5, 22: 9.5, 23: 6.0,     # S04 : 44
        26: 9.5, 27: 4.0, 28: 9.5, 29: 8.5,              # S05 (février), vendredi sans pointage
    },
    "COTTE": {
        5: 8.5, 6: 8.5, 7: 8.5, 8: 8.5, 9: 5.0,          # S02 : 39
        12: 8.5, 13: 8.5, 14: 8.5, 15: 8.5, 16: 5.0,     # S03 : 39
        19: 8.5, 20: 8.5, 21: 5.0, 22: 8.5, 23: 5.0,     # S04 : 35,5 (6h–11h mercredi)
        26: 8.5, 27: 8.5, 28: 8.5, 29: 8.5, 30: 5.0,     # S05 (février)
    },
}
#: Jours du planning à remettre en travail (le setup y pose les absences de Quadra ; ici elles viennent des feuilles).
PLANNING_TRAVAIL = {"GAUTHERON": {13: 8.5, 14: 8.5, 23: 5.0}, "COTTE": {21: 8.5}}
#: Jours de congé d'après la feuille.
PLANNING_CONGE = {"GAUTHERON": {22: 8.5}}
QUADRA_BRUT = {"BUGNY": 3023.40, "COTTE": 2351.89, "ESPINOSA": 3046.68, "GAUTHERON": 2252.28, "GIRERD": 3799.06}


def _generer(employee_id: str):
    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=employee_id, year=YEAR, month=MONTH,
                force_calendrier_incomplet=force,
                requested_by_name="script colorplast_janvier_feuilles_test",
            )
        )
    try:
        return _run(False)
    except PayslipCalendarIncompleteError:
        return _run(True)


def _snapshot(ids: list[str]) -> tuple[dict, list]:
    emps = supabase.table("employees").select("*").in_("id", ids).execute().data or []
    hist = supabase.table("salary_history").select("*").in_("employee_id", ids).execute().data or []
    return {e["id"]: e for e in emps}, hist


def _restaurer(emp_avant: dict, hist_avant: list) -> None:
    ids = list(emp_avant)
    apres = {e["id"]: e for e in (supabase.table("employees").select("*").in_("id", ids).execute().data or [])}
    for emp_id, avant in emp_avant.items():
        diff = {k: v for k, v in avant.items() if k not in ("updated_at",) and apres.get(emp_id, {}).get(k) != v}
        if diff:
            supabase.table("employees").update(diff).eq("id", emp_id).execute()
            print(f"  fiche {avant.get('last_name')} : {sorted(diff)} remis")
    ids_avant = {h["id"] for h in hist_avant}
    hist_apres = supabase.table("salary_history").select("id").in_("employee_id", ids).execute().data or []
    for h in hist_apres:
        if h["id"] not in ids_avant:
            supabase.table("salary_history").delete().eq("id", h["id"]).execute()
    for h in hist_avant:
        supabase.table("salary_history").upsert(h).execute()
    print(f"  historique de salaire : {len(hist_avant)} ligne(s) remise(s), {len([h for h in hist_apres if h['id'] not in ids_avant])} retirée(s)")


def _poser_calendriers(emps: dict) -> None:
    for nom, heures in FEUILLES.items():
        emp = emps[nom]
        sched = (
            supabase.table("employee_schedules").select("id, planned_calendar, actual_hours")
            .match({"employee_id": emp["id"], "year": YEAR, "month": MONTH}).single().execute()
        ).data
        planned = copy.deepcopy(sched.get("planned_calendar") or {})
        par_jour = {int(j["jour"]): j for j in planned.get("calendrier_prevu", [])}
        for jour, h in PLANNING_TRAVAIL.get(nom, {}).items():
            par_jour[jour].update({"type": "travail", "heures_prevues": h, "manuel": True})
            par_jour[jour].pop("origine", None)
        for jour, h in PLANNING_CONGE.get(nom, {}).items():
            par_jour[jour].update({"type": "conges_payes", "heures_prevues": h, "manuel": True, "origine": "absence"})
        planned["calendrier_prevu"] = sorted(par_jour.values(), key=lambda j: int(j["jour"]))
        reel = []
        for j in planned["calendrier_prevu"]:
            jour = int(j["jour"])
            if j.get("type") == "ferie":
                reel.append({"jour": jour, "type": "ferie", "heures_faites": None})
            elif j.get("type") == "conges_payes":
                reel.append({"jour": jour, "type": "conge", "heures_faites": 0.0})
            elif jour in heures:
                reel.append({"jour": jour, "type": "travail", "heures_faites": heures[jour]})
        actual = copy.deepcopy(sched.get("actual_hours") or {})
        actual["periode"] = {"mois": MONTH, "annee": YEAR}
        actual["calendrier_reel"] = reel
        supabase.table("employee_schedules").update(
            {"planned_calendar": planned, "actual_hours": actual}
        ).eq("id", sched["id"]).execute()
        print(f"  {nom:10s} : {len([r for r in reel if r['type'] == 'travail'])} jours pointés posés")
    # Les heures sup du setup (lues sur les bulletins Quadra) laissent la place aux feuilles.
    for nom in ("BUGNY", "ESPINOSA"):
        supabase.table("monthly_inputs").delete().match(
            {"employee_id": emps[nom]["id"], "year": YEAR, "month": MONTH}
        ).ilike("name", "%suppl%").execute()


def main() -> int:
    apply = "--apply" in sys.argv
    emps = {
        e["last_name"]: e
        for e in (supabase.table("employees").select("id, last_name").eq("company_id", COMPANY_ID).in_("last_name", list(SALARIES)).execute()).data or []
    }
    if not apply:
        print("SIMULATION : rien n'est écrit. Feuilles lues :")
        for nom, h in FEUILLES.items():
            print(f"  {nom:10s} {sum(h.values()):.1f} h sur {len(h)} jours")
        return 0

    ids = [e["id"] for e in emps.values()]
    emp_avant, hist_avant = _snapshot(ids)
    print("=== Fiches relevées avant ===")
    for e in emp_avant.values():
        print(f"  {e['last_name']:10s} salaire_de_base={json.dumps(e.get('salaire_de_base'))}")
    rc = 0
    try:
        print("\n=== Setup de janvier (backtest) ===")
        apply_month("Colorplast", YEAR, MONTH)
        print("\n=== Calendriers depuis les feuilles ===")
        _poser_calendriers(emps)
        print("\n=== Génération de janvier ===")
        for nom in SALARIES:
            emp = emps[nom]
            try:
                res = _generer(emp["id"])
            except PayslipBadRequestError as exc:
                print(f"::error::{nom} : {exc}")
                rc = 1
                continue
            data = (
                supabase.table("payslips").select("payslip_data")
                .match({"employee_id": emp["id"], "year": YEAR, "month": MONTH}).single().execute()
            ).data["payslip_data"]
            brut = float(data.get("salaire_brut") or 0)
            en_tete = data.get("en_tete") or {}
            ecart = brut - QUADRA_BRUT[nom]
            etat = "OK" if abs(ecart) <= 0.05 else "ECART"
            print(f"\n{etat:5s} {nom:10s} brut {brut:.2f} — Quadra {QUADRA_BRUT[nom]:.2f} — écart {ecart:+.2f} ; fenêtre {en_tete.get('date_debut_variables')} → {en_tete.get('date_fin_variables')} ; {res.status}")
            for ligne in data.get("calcul_du_brut") or []:
                lib = str(ligne.get("libelle", ""))
                if "suppl" in lib.lower() and "structur" not in lib.lower():
                    print(f"      HS      {lib[:50]:50s} q={ligne.get('quantite')} +{ligne.get('gain')}")
            for cle in ("details_absences", "details_conges"):
                for ligne in data.get(cle) or []:
                    print(f"      {cle[8:15]:7s} {str(ligne.get('libelle'))[:50]:50s} q={ligne.get('quantite')} -{ligne.get('perte')} +{ligne.get('gain')}")
            for w in res.warnings or []:
                print(f"      avertissement : {w}")
            if etat != "OK":
                rc = 1
    finally:
        print("\n=== Fiches remises comme avant ===")
        _restaurer(emp_avant, hist_avant)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
