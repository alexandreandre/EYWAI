"""Restaure employees.salaire_de_base Colorplast.

Vérité retenue par salarié :
  - salary_history : si une augmentation postérieure à mai existe, elle fait foi
    (cas DEMORY et FUCKAR, effective au 01/06/2026) ;
  - sinon le bulletin de MAI, non régénéré (21/07), témoin de l'état production.
"""
from app.core.database import supabase, get_supabase_admin_client
import copy, sys

CID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
APPLY = "--apply" in sys.argv

emps = supabase.table("employees").select("id,last_name,salaire_de_base").eq("company_id", CID).execute().data
hist = supabase.table("salary_history").select("*").eq("company_id", CID).execute().data
hist_by_emp = {}
for h in hist:
    hist_by_emp.setdefault(h["employee_id"], []).append(h)

plan = []
print(f"{'salarié':16} {'actuel':>9} {'vérité':>9}  source")
for e in sorted(emps, key=lambda x: x["last_name"]):
    sdb = e.get("salaire_de_base") or {}
    actuel = float((sdb.get("valeur") if isinstance(sdb, dict) else sdb) or 0)

    posterieures = sorted(
        (h for h in hist_by_emp.get(e["id"], []) if h["effective_date"] > "2026-05-31"),
        key=lambda h: h["effective_date"],
    )
    if posterieures:
        ref = float((posterieures[-1].get("nouveau_salaire") or {}).get("valeur") or 0)
        source = f"salary_history {posterieures[-1]['effective_date']}"
    else:
        ps = supabase.table("payslips").select("payslip_data").match(
            {"employee_id": e["id"], "year": 2026, "month": 5}).maybe_single().execute()
        if not ps or not ps.data:
            print(f"  {e['last_name']:16} {actuel:>9}        —  pas de bulletin mai, ignoré")
            continue
        lignes = (ps.data["payslip_data"] or {}).get("calcul_du_brut") or []
        g = next((l.get("gain") for l in lignes
                  if str(l.get("libelle") or "").strip().lower() == "salaire de base"), None)
        if g is None:
            print(f"  {e['last_name']:16} {actuel:>9}        —  ligne absente, ignoré")
            continue
        ref = float(g)
        source = "bulletin mai"

    ecart = round(ref - actuel, 2)
    marque = "OK" if abs(ecart) < 0.005 else f"RESTAURER {ecart:+.2f}"
    print(f"  {e['last_name']:16} {actuel:>9} {ref:>9}  {source} — {marque}")
    if abs(ecart) >= 0.005:
        plan.append((e, ref))

if not plan:
    print("\nRien à restaurer.")
    sys.exit(0)
if not APPLY:
    print(f"\n{len(plan)} à restaurer — relancer avec --apply")
    sys.exit(0)

admin = get_supabase_admin_client()
for e, ref in plan:
    sdb = copy.deepcopy(e.get("salaire_de_base") or {"type": "mensuel"})
    sdb["valeur"] = ref
    admin.table("employees").update({"salaire_de_base": sdb}).eq("id", e["id"]).execute()
    print(f"  restauré {e['last_name']} -> {ref}")
