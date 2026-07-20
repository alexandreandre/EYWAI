"""Sauvegarde / restauration SÛRE de l'état MBC (backup persistant, non éphémère).

  python -m scripts.backtest.mbc_dbsafe backup
  python -m scripts.backtest.mbc_dbsafe restore employees   # config PARTAGÉE (salaire_de_base, specif, seniority, contrat, classif, mutuelle_type_ids)
  python -m scripts.backtest.mbc_dbsafe restore mutuelle     # company_mutuelle_types
  python -m scripts.backtest.mbc_dbsafe restore all          # employees + mutuelle (config partagée complète)

Le backup est dans backend/scripts/backtest/_mbc_backup/ (persiste entre sessions).
IMPORTANT : `restore employees` remet le salaire_de_base (champ PARTAGÉ tous mois) à
l'état sauvegardé — c'est le filet obligatoire après tout base-flip (cf. incident :
un flip non restauré a fait tomber MBC mai de 61/75 à 9/75)."""
import os
import sys
import json

sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import resolve_company_id

BK = os.path.join(os.path.dirname(__file__), "_mbc_backup")
EMP_SHARED = ("specificites_paie", "seniority_reference_date", "salaire_de_base",
              "contract_type", "classification_conventionnelle", "duree_hebdomadaire",
              "mutuelle_type_ids")


def backup():
    os.makedirs(BK, exist_ok=True)
    admin = get_supabase_admin_client()
    cid = resolve_company_id("Mont Blanc Composite")
    emps = admin.table("employees").select("*").eq("company_id", cid).execute().data
    json.dump(emps, open(f"{BK}/employees.json", "w"), default=str, indent=0)
    mt = admin.table("company_mutuelle_types").select("*").eq("company_id", cid).execute().data
    json.dump(mt, open(f"{BK}/company_mutuelle_types.json", "w"), default=str, indent=0)
    print(f"backup OK -> {BK} : employees={len(emps)} mutuelle_types={len(mt)}")


def restore_employees():
    admin = get_supabase_admin_client()
    emps = json.load(open(f"{BK}/employees.json"))
    for e in emps:
        upd = {k: e.get(k) for k in EMP_SHARED if k in e}
        admin.table("employees").update(upd).eq("id", e["id"]).execute()
    print("restored employees shared config:", len(emps))


def restore_mutuelle():
    admin = get_supabase_admin_client()
    mt = json.load(open(f"{BK}/company_mutuelle_types.json"))
    for r in mt:
        admin.table("company_mutuelle_types").update(
            {k: r.get(k) for k in ("libelle", "montant_salarial", "montant_patronal",
                                   "part_patronale_soumise_a_csg", "is_active",
                                   "pack_couverture", "statut_categoriel", "source") if k in r}
        ).eq("id", r["id"]).execute()
    print("restored mutuelle types:", len(mt))


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "backup"
    if action == "backup":
        backup()
    elif action == "restore":
        what = sys.argv[2] if len(sys.argv) > 2 else "all"
        if what in ("employees", "all"):
            restore_employees()
        if what in ("mutuelle", "all"):
            restore_mutuelle()
    else:
        print("usage: mbc_dbsafe.py backup | restore [employees|mutuelle|all]")
