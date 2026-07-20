"""Mesure convergence tier-S en parallèle (threads, PDF stub). 
Usage: measure_par.py <Company> <year> <month> [--workers N] [--no-regen] [MATRICULE...]"""
import sys
sys.path.insert(0,"/Users/alex/Desktop/EYWAI/EYWAI/backend")
import weasyprint
def _stub(self,target=None,*a,**k):
    if target is None: return b"%PDF-1.4\n%stub\n"
    if hasattr(target,"write"): target.write(b"%PDF-1.4\n%stub\n"); return None
    open(target,"wb").write(b"%PDF-1.4\n%stub\n"); return None
weasyprint.HTML.write_pdf=_stub
import app.modules.payroll.documents.payslip_generator as _pg
class _FB:
    def upload(self,*a,**k): return None
    def create_signed_url(self,*a,**k): return {"signedURL":"stub"}
try: _pg.supabase.storage.from_=lambda *a,**k:_FB()
except Exception: pass
import app.modules.employee_loans.application.payroll_integration as _pi
_pi.enrich_payslip_after_upsert=lambda data,*a,**k: data
from concurrent.futures import ThreadPoolExecutor
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.backtest_company_payroll import _generate_payslip, compare_matches
from app.modules.payroll.backtest.thresholds import default_thresholds

company=sys.argv[1]; year=int(sys.argv[2]); month=int(sys.argv[3])
args=sys.argv[4:]
workers=6
if "--workers" in args:
    i=args.index("--workers"); workers=int(args[i+1]); args=args[:i]+args[i+2:]
regen="--no-regen" not in args
wanted=set(a for a in args if not a.startswith("--"))
import json as _json
_dump=None
if "--dump-json" in args:
    _j=args.index("--dump-json"); _dump=args[_j+1]; args=args[:_j]+args[_j+2:]
    wanted=set(a for a in args if not a.startswith("--"))
pdf=resolve_bulletin_pdf(company,year,month)
refs=load_reference_bulletins(company,year,month,pdf_path=pdf)
cid=resolve_company_id(company)
matched=match_employees(cid,refs).matched
if wanted: matched=[m for m in matched if m.matricule in wanted]
errs=[]
if regen:
    def gen(m):
        try: _generate_payslip(m,year,month); return None
        except Exception as e: return f"{m.matricule}: {e}"
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(gen,matched):
            if r: errs.append(r)
for e in errs[:20]: print("[GENERR]",e,flush=True)
reports=compare_matches(matched,year,month,thresholds=default_thresholds(),systemic_deltas={},correction_attempts={})
reports.sort(key=lambda r:r.tier_s_max_delta)
nconv=sum(1 for r in reports if r.tier_s_max_delta<=0.05)
nsub1=sum(1 for r in reports if r.tier_s_max_delta<1.0)
nsub20=sum(1 for r in reports if r.tier_s_max_delta<=20.0)
print(f"\n=== {company} {year}-{month:02d} : {nconv}/{len(reports)} convergés, {nsub1} <1e, {nsub20} <=20e (genErr={len(errs)}) ===")
if _dump:
    _o={}
    for r in reports:
        bd=next((ln.delta for ln in r.lines if ln.field_key=="salaire_brut"),0.0)
        _o[r.matricule]={"tierS":round(r.tier_s_max_delta,2),"brut":round(bd,2)}
    _json.dump(_o,open(_dump,"w"))
for r in reports:
    d=r.tier_s_max_delta
    if d<=0.05: continue
    lines=[f"{ln.field_key}={ln.delta:+.2f}" for ln in r.lines if ln.field_key in {"salaire_brut","net_imposable","montant_net_social","net_a_payer","pas_montant"} and abs(ln.delta)>0.05]
    print(f"  {r.matricule:16s} {d:9.2f}  {' '.join(lines)}")
