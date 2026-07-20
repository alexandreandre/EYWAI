"""Verification LIGNE PAR LIGNE : compare les rubriques generees par EYWAI aux
lignes du bulletin reel, pour detecter des erreurs qui se compenseraient au
niveau des 5 figures du tier-S. Usage: verif_lignes.py <year> <month> MAT..."""
import sys
import re

sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf

YEAR = int(sys.argv[1]); MONTH = int(sys.argv[2]); wanted = set(sys.argv[3:])
admin = get_supabase_admin_client()
pdf = resolve_bulletin_pdf("Mont Blanc Composite", YEAR, MONTH)
refs = load_reference_bulletins("Mont Blanc Composite", YEAR, MONTH, pdf_path=pdf)
cid = resolve_company_id("Mont Blanc Composite")
matched = [m for m in match_employees(cid, refs).matched if m.matricule in wanted]
_NUM = re.compile(r"(\d[\d ]*\.\d{2})")


def bulletin_montant(text, libelle_frag):
    """Cherche une ligne du bulletin contenant le fragment et renvoie ses nombres."""
    for ln in (text or "").split("\n"):
        if libelle_frag.lower() in ln.lower():
            nums = [n.replace(" ", "") for n in _NUM.findall(ln)]
            return ln.strip()[:70], nums
    return None, []


for m in matched:
    r = (admin.table("payslips").select("payslip_data")
         .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH})
         .order("created_at", desc=True).limit(1).execute().data)
    d = (r[0]["payslip_data"] if r else {}) or {}
    txt = m.reference.raw_text or ""
    print(f"\n========== {m.matricule} ==========")
    # BRUT : composantes
    print("-- BRUT (EYWAI) --")
    for l in d.get("calcul_du_brut", []):
        g = l.get("gain") or 0
        if abs(g) > 0.001:
            print(f"   {l.get('libelle','')[:34]:34s} q={l.get('quantite')} t={l.get('taux')}  = {g}")
    # COTISATIONS salariales : chaque montant EYWAI doit exister dans le bulletin
    # (recherche par VALEUR sur tout le texte -> detecte une ligne inventee ou
    # fausse qui se compenserait ailleurs).
    all_nums = {float(n.replace(" ", "")) for n in _NUM.findall(txt)}
    print("-- COTISATIONS salariales : montant EYWAI présent au bulletin ? --")
    manquants = 0
    for grp in d.get("cotisations_officielles", []):
        for l in grp.get("lignes", []):
            ms = l.get("montant_salarial")
            if ms is None or abs(ms) < 0.01:
                continue
            lib = l.get("libelle", "")[:32]
            present = any(abs(v - abs(ms)) <= 0.10 for v in all_nums)
            if present:
                print(f"   OK   {lib:32s} {ms:9.2f}")
            else:
                manquants += 1
                print(f"   ⚠MANQUE {lib:32s} {ms:9.2f}  (aucun montant proche au bulletin)")
    print(f"   -> {manquants} ligne(s) sans correspondance de montant")
