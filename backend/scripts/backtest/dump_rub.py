"""Dump rubriques EYWAI generees vs lignes bulletin pour des matricules MBC.
Usage: dump_rub.py <year> <month> MAT [MAT...]"""
import sys, json
sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
import weasyprint
def _stub(self, target=None, *a, **k):
    if target is None: return b"%PDF-1.4\n%stub\n"
    if hasattr(target, "write"): target.write(b"%PDF-1.4\n%stub\n"); return None
    open(target, "wb").write(b"%PDF-1.4\n%stub\n"); return None
weasyprint.HTML.write_pdf = _stub
import app.modules.payroll.documents.payslip_generator as _pg
class _FB:
    def upload(self, *a, **k): return None
    def create_signed_url(self, *a, **k): return {"signedURL": "stub"}
try: _pg.supabase.storage.from_ = lambda *a, **k: _FB()
except Exception: pass
import app.modules.employee_loans.application.payroll_integration as _pi
_pi.enrich_payslip_after_upsert = lambda data, *a, **k: data
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.backtest_company_payroll import _generate_payslip
COMPANY = "Mont Blanc Composite"
year = int(sys.argv[1]); month = int(sys.argv[2]); wanted = set(sys.argv[3:])
pdf = resolve_bulletin_pdf(COMPANY, year, month)
refs = load_reference_bulletins(COMPANY, year, month, pdf_path=pdf)
cid = resolve_company_id(COMPANY)
matched = [m for m in match_employees(cid, refs).matched if m.matricule in wanted]

def walk(d, out, pfx=""):
    if isinstance(d, dict):
        lib = d.get("libelle") or d.get("label") or d.get("name")
        montant = d.get("montant") or d.get("montant_salarial") or d.get("amount")
        base = d.get("base") or d.get("nombre") or d.get("quantite")
        if lib and (montant is not None):
            out.append((str(lib)[:38], base, montant))
        for v in d.values():
            walk(v, out, pfx)
    elif isinstance(d, list):
        for v in d: walk(v, out, pfx)

for m in matched:
    data = _generate_payslip(m, year, month)
    print(f"\n===== EYWAI {m.matricule} (brut={data.get('salaire_brut') or data.get('brut')}) =====")
    out = []
    walk(data, out)
    seen = set()
    for lib, base, mont in out:
        key = (lib, str(mont))
        if key in seen: continue
        seen.add(key)
        try: mv = float(mont)
        except Exception: mv = None
        if mv is not None and abs(mv) > 0.001:
            print(f"  {lib:38s} base={base}  montant={mont}")
