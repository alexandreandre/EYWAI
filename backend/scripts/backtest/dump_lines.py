"""Génère UN bulletin EYWAI (PDF/stockage stubés) et affiche ses lignes, pour
le comparer à la main au bulletin réel. Générique : société en argument.

Usage: dump_lines.py <Company> <year> <month> MAT [MAT...]
"""
import sys
sys.path.insert(0, "/Users/alex/Desktop/EYWAI/EYWAI/backend")
import weasyprint


def _stub(self, target=None, *a, **k):
    if target is None:
        return b"%PDF-1.4\n%stub\n"
    if hasattr(target, "write"):
        target.write(b"%PDF-1.4\n%stub\n"); return None
    open(target, "wb").write(b"%PDF-1.4\n%stub\n"); return None


weasyprint.HTML.write_pdf = _stub
import app.modules.payroll.documents.payslip_generator as _pg


class _FB:
    def upload(self, *a, **k): return None
    def create_signed_url(self, *a, **k): return {"signedURL": "stub"}


try:
    _pg.supabase.storage.from_ = lambda *a, **k: _FB()
except Exception:
    pass
import app.modules.employee_loans.application.payroll_integration as _pi
_pi.enrich_payslip_after_upsert = lambda data, *a, **k: data
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins, find_reference_pdf
from scripts.backtest.bulletins_source import resolve_bulletin_pdf
from scripts.backtest.backtest_company_payroll import _generate_payslip

company = sys.argv[1]
year = int(sys.argv[2]); month = int(sys.argv[3]); wanted = set(sys.argv[4:])
try:
    pdf = resolve_bulletin_pdf(company, year, month)
except FileNotFoundError:
    pdf = find_reference_pdf(company, year, month)
refs = load_reference_bulletins(company, year, month, pdf_path=pdf)
cid = resolve_company_id(company)
matched = [m for m in match_employees(cid, refs, year, month).matched if m.matricule in wanted]


def walk(d, out):
    if isinstance(d, dict):
        lib = d.get("libelle") or d.get("label") or d.get("name")
        montant = d.get("montant")
        if montant is None:
            montant = d.get("montant_salarial")
        if montant is None:
            montant = d.get("gain") if d.get("gain") is not None else d.get("perte")
        if montant is None:
            montant = d.get("amount")
        base = d.get("base") if d.get("base") is not None else d.get("quantite")
        pat = d.get("montant_patronal")
        if lib and (montant is not None):
            out.append((str(lib)[:44], base, montant, pat))
        for v in d.values():
            walk(v, out)
    elif isinstance(d, list):
        for v in d:
            walk(v, out)


for m in matched:
    try:
        data = _generate_payslip(m, year, month)
    except Exception as exc:  # noqa: BLE001
        print(f"\n===== EYWAI {m.matricule} : ERREUR {exc!r}")
        continue
    # Le générateur renvoie une enveloppe {status, message, payslip_id, warnings} ;
    # le bulletin lui-même est relu en base.
    if isinstance(data, dict) and "salaire_brut" not in data:
        print(f"\n----- {m.matricule} : status={data.get('status')} message={str(data.get('message'))[:200]} "
              f"warnings={data.get('warnings')}")
        pid = data.get("payslip_id")
        if pid:
            row = (_pg.supabase.table("payslips").select("payslip_data, generated_at")
                   .eq("id", pid).single().execute().data)
            print(f"      generated_at={row.get('generated_at')}")
            data = row.get("payslip_data") or {}
    if not isinstance(data, dict) or "salaire_brut" not in data:
        print(f"\n===== EYWAI {m.matricule} : structure inattendue, clés={list(data)[:12] if isinstance(data, dict) else type(data)}")
        continue
    syn = data.get("synthese_net") or {}
    print(f"\n===== EYWAI {m.matricule} {month:02d}/{year} brut={data.get('salaire_brut')} "
          f"NI={syn.get('net_imposable')} MNS={syn.get('montant_net_social')} "
          f"NAP={data.get('net_a_payer')} PAS={(syn.get('impot_prelevement_a_la_source') or {}).get('montant')}")
    ref = m.reference
    print(f"      REEL  brut={ref.salaire_brut} NI={ref.net_imposable} MNS={ref.montant_net_social} "
          f"NAP={ref.net_a_payer} PAS={ref.pas_montant if hasattr(ref, 'pas_montant') else '?'}")
    out = []
    walk(data.get("calcul_du_brut"), out)
    walk(data.get("cotisations_officielles"), out)
    walk(data.get("primes_non_soumises"), out)
    walk(data.get("retenues_saisies"), out)
    walk(data.get("revenus_hors_brut_imposables"), out)
    seen = set()
    for lib, base, mont, pat in out:
        key = (lib, str(mont), str(pat))
        if key in seen:
            continue
        seen.add(key)
        try:
            mv = float(mont)
        except Exception:  # noqa: BLE001
            mv = None
        if mv is not None and (abs(mv) > 0.001 or (pat and abs(float(pat)) > 0.001)):
            print(f"  {lib:44s} base={base}  sal={mont}  pat={pat}")
    print("  synthese:", {k: v for k, v in syn.items() if not isinstance(v, dict)})
