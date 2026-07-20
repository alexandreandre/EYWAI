#!/usr/bin/env python3
"""Flip du taux PAS par mois, GÉNÉRIQUE (toute entreprise), via `pdftotext -layout`.

Le taux PAS vit dans `specificites_paie.prelevement_a_la_source.taux`, champ PARTAGÉ
entre tous les mois (comme salaire_de_base). Or le taux réel varie souvent mois à mois
(ex. CHAMBERT Comitech : jan 6.80 % puis fév-juin 5.90 %). Sans flip, un mois est calculé
avec le taux d'un autre -> PAS faux -> net à payer faux de ±20-30 €.

Contrairement à flip_pas_all (câblé MBC + raw_text page 1), ce script lit le PDF en
-layout donc capte la ligne PAS même en page 2 (net-only). Idempotent ; ⚠ champ partagé
-> restaurer après (mbc_dbsafe / comitech backup) ou re-flipper au mois voulu avant mesure.

Usage: flip_pas_layout.py "<Company>" <year> <month> [--dry] [MATRICULE...]
"""
import sys
import re
import copy
import subprocess

sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf

COMPANY = sys.argv[1]
YEAR = int(sys.argv[2]); MONTH = int(sys.argv[3])
DRY = "--dry" in sys.argv
wanted = set(a for a in sys.argv[4:] if not a.startswith("--"))

# "Impôt sur le revenu prélevé à la source  <base>  <taux>  <montant> ..."
_PAS_RE = re.compile(
    r"Imp[ôo]t sur le revenu pr[ée]lev[ée] [àa] la source\s+[\d ]+\.\d{2}\s+([\d]+\.\d{2})"
)


def _matricule_taux(pdf: str) -> dict:
    """Mappe matricule -> taux PAS en découpant le -layout par 'Matricule :'."""
    lines = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                           capture_output=True, text=True).stdout.split("\n")
    out, cur = {}, None
    for ln in lines:
        m = re.search(r"Matricule\s*:\s*(\S+)", ln)
        if m:
            cur = m.group(1)
        hit = _PAS_RE.search(ln)
        if hit and cur:
            out.setdefault(cur, float(hit.group(1)))
    return out


admin = get_supabase_admin_client()
pdf = resolve_bulletin_pdf(COMPANY, YEAR, MONTH)
refs = load_reference_bulletins(COMPANY, YEAR, MONTH, pdf_path=pdf)
cid = resolve_company_id(COMPANY)
matched = match_employees(cid, refs).matched
if wanted:
    matched = [m for m in matched if m.matricule in wanted]
matched.sort(key=lambda m: m.matricule)

taux_map = _matricule_taux(pdf)
n = 0
skipped = []
for m in matched:
    taux = taux_map.get(m.matricule)
    if taux is None:
        skipped.append(m.matricule)
        continue
    emp = (admin.table("employees").select("specificites_paie")
           .eq("id", m.employee_id).single().execute().data)
    sp = copy.deepcopy(emp.get("specificites_paie") or {})
    pas = sp.setdefault("prelevement_a_la_source", {})
    cur = pas.get("taux")
    if DRY:
        if abs((cur if cur is not None else -1) - taux) > 0.001:
            print(f"  {m.matricule:16s} config={cur} -> bulletin={taux}")
        continue
    if abs((cur if cur is not None else -1) - taux) > 0.001:
        pas["taux"] = taux
        admin.table("employees").update({"specificites_paie": sp}).eq("id", m.employee_id).execute()
        n += 1
print(f"=== flip_pas_layout {COMPANY} {MONTH:02d}: {n} taux PAS flippés, {len(skipped)} sans ligne PAS ===")
