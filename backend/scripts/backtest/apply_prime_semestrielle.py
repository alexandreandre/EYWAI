"""Pose la « BSEM Prime semestrielle » (prime de juin, fin de 1er semestre) en
prime TAXÉE (soumise cotisations + impôt). Additif et idempotent : n'ajoute que
si absente (ne touche AUCUN autre monthly_input -> ne casse pas la curation
revert-safe du reconciliateur). Month-scoped -> sans risque pour les autres mois.

Le montant est dans la colonne « Montant salarial » du PDF (pas en fin de ligne),
comme la base forfait -> extraction par position de colonne (cf. flip_base_all).
Vérifié au centime = delta brut (GAUDEY 1179,96 ; BOUVIERP 835,60 ; PORRAL 1111,39).

Usage: apply_prime_semestrielle.py <year> <month> [--dry] [MATRICULE...]"""
import sys
import re

sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf

COMPANY = "Mont Blanc Composite"
YEAR = int(sys.argv[1]); MONTH = int(sys.argv[2])
DRY = "--dry" in sys.argv
wanted = set(a for a in sys.argv[3:] if not a.startswith("--"))

_NUM = re.compile(r"\d[\d ]*\.\d{2}")
_HDR = re.compile(r"Rubriques.*Montant salarial.*Mt patronal")
LABEL = "BSEM Prime semestrielle"
INPUT_NAME = "Prime semestrielle"


def _zone(lines):
    for ln in lines:
        if _HDR.search(ln):
            return ln.index("Montant salarial"), ln.index("Mt patronal")
    return None


def _montant(text):
    lines = (text or "").split("\n")
    z = _zone(lines)
    if z is None:
        return None
    for ln in lines:
        if LABEL in ln:
            cands = [m for m in _NUM.finditer(ln) if z[0] < m.end() <= z[1]]
            if len(cands) == 1:
                return round(float(cands[0].group(0).replace(" ", "")), 2)
    return None


admin = get_supabase_admin_client()
pdf = resolve_bulletin_pdf(COMPANY, YEAR, MONTH)
refs = load_reference_bulletins(COMPANY, YEAR, MONTH, pdf_path=pdf)
cid = resolve_company_id(COMPANY)
matched = match_employees(cid, refs).matched
if wanted:
    matched = [m for m in matched if m.matricule in wanted]

n = 0
for m in matched:
    montant = _montant(m.reference.raw_text or "")
    if not montant:
        continue
    existing = (admin.table("monthly_inputs").select("id,name")
                .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH}).execute().data or [])
    if any(INPUT_NAME.lower() in (r.get("name") or "").lower() for r in existing):
        continue  # déjà posée -> idempotent
    if DRY:
        print(f"  {m.matricule:14s} Prime semestrielle = {montant}")
        continue
    admin.table("monthly_inputs").insert({
        "employee_id": m.employee_id, "company_id": cid, "year": YEAR, "month": MONTH,
        "name": INPUT_NAME, "amount": montant,
        "is_socially_taxed": True, "is_taxable": True,
    }).execute()
    n += 1
print(f"=== apply_prime_semestrielle {YEAR}-{MONTH:02d}: {n} primes posées ===")
