"""Flip du TAUX PAS au mois historique, depuis la ligne bulletin
« Impot sur le revenu preleve a la source <base> <taux> ».

Pourquoi : le taux PAS vit dans employees.specificites_paie.prelevement_a_la_source
.taux -- un champ PARTAGE entre tous les mois (comme salaire_de_base). Le
reconciliateur ne l'ecrit que pour le mois courant ; bulk_apply_month ne l'ecrit
pas du tout. Sans flip, un mois historique est calcule avec le taux PAS de mai
-> PAS faux (ex. janvier : OVIE pas=+191, ADAMYOUSSE pas=-8, PFISTER pas=+16).

Sequentiel DB-only. Revert OBLIGATOIRE via mbc_dbsafe.py restore employees
(specificites_paie est sauvegarde par le backup).
Usage: flip_pas_all.py <year> <month> [--dry] [MATRICULE...]"""
import sys
import re
import copy

sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf

COMPANY = "Mont Blanc Composite"
YEAR = int(sys.argv[1]); MONTH = int(sys.argv[2])
DRY = "--dry" in sys.argv
wanted = set(a for a in sys.argv[3:] if not a.startswith("--"))

_PAS_RE = re.compile(
    r"Imp[ôo]t sur le revenu pr[ée]lev[ée] [àa] la source\s+[\d.]+\s+([\d]+\.\d{2})"
)

admin = get_supabase_admin_client()
pdf = resolve_bulletin_pdf(COMPANY, YEAR, MONTH)
refs = load_reference_bulletins(COMPANY, YEAR, MONTH, pdf_path=pdf)
cid = resolve_company_id(COMPANY)
matched = match_employees(cid, refs).matched
if wanted:
    matched = [m for m in matched if m.matricule in wanted]
matched.sort(key=lambda m: m.matricule)

n = 0
skipped = []
for m in matched:
    hit = _PAS_RE.search(m.reference.raw_text or "")
    if not hit:
        skipped.append(m.matricule)
        continue
    taux = float(hit.group(1))
    emp = (admin.table("employees").select("specificites_paie")
           .eq("id", m.employee_id).single().execute().data)
    sp = copy.deepcopy(emp.get("specificites_paie") or {})
    pas = sp.setdefault("prelevement_a_la_source", {})
    cur = pas.get("taux")
    if DRY:
        print(f"  {m.matricule:16s} config={cur} -> bulletin={taux}")
        continue
    if abs((cur if cur is not None else -1) - taux) > 0.001:
        pas["taux"] = taux
        admin.table("employees").update({"specificites_paie": sp}).eq("id", m.employee_id).execute()
        n += 1
print(f"=== flip_pas_all {MONTH:02d}: {n} taux PAS flippes, {len(skipped)} sans ligne PAS ===")
