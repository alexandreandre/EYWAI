"""Feuilles de pointage de janvier 2026 de Colorplast, et leur pose.

Lues sur `data/colorplast/pointages/2026-01/` (S02 à S05), avec la règle de
Gaëlle annotée sur la feuille S03 : heures = fin − début − 0,5 h de pause quand
la journée dépasse 6 h. Prénoms → salariés : Marion = Gautheron, Michel = Bugny,
Anthony = Espinosa, Léo = Cotte. Girerd (cadre) n'a pas de feuille : mois sans
pointage, planning repris tel quel.

Ce qui vient des feuilles et non du setup : les absences (Gautheron 13 et 14/01,
Cotte 21/01) et les heures sup (Bugny, Espinosa). Le congé de Gautheron est posé
le jeudi 22 comme sur la feuille (Quadra l'a daté du 23).

Seul janvier est monté depuis les feuilles ; les mois suivants prennent les
heures sup que le cabinet a réellement payées. Voir
`scripts/colorplast_rejeu_test.py`.
"""

from __future__ import annotations

import copy

from app.core.database import supabase

YEAR, MOIS = 2026, 1

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
        19: 10.0, 20: 10.0, 21: 10.0, 22: 10.5, 23: 8.5, # S04 : 49 (vendredi 7h–16h, « 8,5 » annoté par Gaëlle)
        26: 10.0, 27: 10.0, 28: 10.0, 29: 10.5, 30: 5.0, # S05 : 45,5 (février)
    },
    "ESPINOSA": {
        # S02 : la feuille donne 44 h (6h–16h ×4, 6h–12h). Quadra paie 4 h à 50 %
        # sur janvier, ce qui suppose 45 h cette semaine dans la saisie de Gaëlle
        # (S03 et S04 sont annotées 44 de sa main). Aligné sur sa saisie : +1 h le
        # lundi, à confirmer avec elle.
        5: 10.5, 6: 9.5, 7: 9.5, 8: 9.5, 9: 6.0,         # S02 : 45 (aligné Quadra)
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


def poser_les_feuilles(emps: dict) -> None:
    for nom, heures in FEUILLES.items():
        emp = emps[nom]
        sched = (
            supabase.table("employee_schedules").select("id, planned_calendar, actual_hours")
            .match({"employee_id": emp["id"], "year": YEAR, "month": MOIS}).single().execute()
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
        actual["periode"] = {"mois": MOIS, "annee": YEAR}
        actual["calendrier_reel"] = reel
        supabase.table("employee_schedules").update(
            {"planned_calendar": planned, "actual_hours": actual}
        ).eq("id", sched["id"]).execute()
        print(f"  {nom:10s} : {len([r for r in reel if r['type'] == 'travail'])} jours pointés posés")
    # Les heures sup du setup (lues sur les bulletins Quadra) laissent la place aux feuilles.
    for nom in ("BUGNY", "ESPINOSA"):
        if nom not in emps:
            continue  # rejeu limité à un salarié
        supabase.table("monthly_inputs").delete().match(
            {"employee_id": emps[nom]["id"], "year": YEAR, "month": MOIS}
        ).ilike("name", "%suppl%").execute()
