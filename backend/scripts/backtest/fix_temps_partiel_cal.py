"""Corrige le calendrier des TEMPS PARTIEL : heures_prevues des jours travail/CP
= duree_hebdomadaire / 5, au lieu du template temps-plein 7,5 h/j.

Pourquoi : le planned_calendar importe un template PLEIN (7,5 h/j) meme pour un
salarie a temps partiel. Le moteur compare alors les heures reelles au template
plein -> il fabrique des HEURES COMPLEMENTAIRES FICTIVES -> brut trop haut.
Constat (MBC janvier) : LIKA (20,08 h/sem -> 4,02 h/j) et RABBENI (17,49 -> 3,50)
avaient 7,5 h/j en janvier alors que MAI etait deja corrige -> +1087 et +682 de brut.

Ne touche QUE le mois demande (planned_calendar est month-scoped, donc SANS risque
pour les autres mois -- contrairement a salaire_de_base qui est partage).
Usage: fix_temps_partiel_cal.py <year> <month> [--dry] [--seuil 35]"""
import sys
import copy

sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id

COMPANY = "Mont Blanc Composite"
YEAR = int(sys.argv[1]); MONTH = int(sys.argv[2])
DRY = "--dry" in sys.argv
SEUIL = 35.0
if "--seuil" in sys.argv:
    SEUIL = float(sys.argv[sys.argv.index("--seuil") + 1])

admin = get_supabase_admin_client()
cid = resolve_company_id(COMPANY)
emps = admin.table("employees").select("id,last_name,first_name,duree_hebdomadaire").eq("company_id", cid).execute().data

n = 0
for e in emps:
    duree = e.get("duree_hebdomadaire")
    if not duree or float(duree) >= SEUIL:
        continue  # temps plein -> hors scope
    cible = round(float(duree) / 5.0, 2)
    s = (admin.table("employee_schedules").select("id,planned_calendar")
         .match({"employee_id": e["id"], "year": YEAR, "month": MONTH}).maybe_single().execute())
    if not s or not s.data:
        continue
    planned = copy.deepcopy(s.data.get("planned_calendar") or {})
    cal = planned.get("calendrier_prevu") or []
    changed = 0
    for j in cal:
        if j.get("type") in ("travail", "conges_payes"):
            if abs(float(j.get("heures_prevues") or 0) - cible) > 0.005:
                j["heures_prevues"] = cible
                changed += 1
    nom = f"{e.get('last_name')} {e.get('first_name')}"
    if not changed:
        continue
    if DRY:
        print(f"  {nom:28s} duree={duree} -> {cible} h/j  ({changed} jours a corriger)")
    else:
        planned["calendrier_prevu"] = cal
        admin.table("employee_schedules").update({"planned_calendar": planned}).eq("id", s.data["id"]).execute()
        print(f"  {nom:28s} duree={duree} -> {cible} h/j  ({changed} jours corriges)")
        n += 1
print(f"=== fix_temps_partiel_cal {YEAR}-{MONTH:02d}: {n} salaries corriges (seuil {SEUIL} h) ===")
