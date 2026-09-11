"""Génère les bulletins d'un mois et les compare à la DSN du cabinet, pour un
mois sans bulletins de référence (ex. juin 2026 MAJI / ZONE 404).

Cibles DSN, par salarié (bloc S21.G00.30.002 = nom) :
  brut          S21.G00.51.011 = 001 (rémunération brute non plafonnée)
  net imposable S21.G00.50.002
  PAS           S21.G00.50.009
  MNS           S21.G00.58.003 = 03 → .004

Usage: dsn_compare.py <Company> <year> <month> [--workers N] [--no-regen] [MAT...]
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

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.core.database import supabase
from scripts.backtest.employee_matching import EmployeeMatch, resolve_company_id, _present_in_month
from scripts.backtest.pdf_loader import RACINE_DATA, dossier_societe
from scripts.backtest.backtest_company_payroll import _generate_payslip, _load_payslip_data

company = sys.argv[1]; year = int(sys.argv[2]); month = int(sys.argv[3])
args = sys.argv[4:]
workers = 3
if "--workers" in args:
    i = args.index("--workers"); workers = int(args[i + 1]); args = args[:i] + args[i + 2:]
regen = "--no-regen" not in args
wanted = {a for a in args if not a.startswith("--")}


def _normalize(s: str) -> str:
    return "".join(c for c in (s or "").upper() if c.isalnum())


def parse_dsn(path: Path) -> dict:
    out: dict = {}
    nom = None; code51 = None; type58 = None
    for line in open(path, encoding="iso-8859-1"):
        k, _, v = line.strip().partition(","); v = v.strip("'")
        if k == "S21.G00.30.002":
            nom = v; out[nom] = {"51": {}, "58": {}}
        elif nom is None:
            continue
        elif k == "S21.G00.30.004":
            out[nom]["prenom"] = v
        elif k == "S21.G00.50.002":
            out[nom]["net_imposable"] = float(v)
        elif k == "S21.G00.50.009":
            out[nom]["pas"] = float(v)
        elif k == "S21.G00.50.006":
            out[nom]["pas_taux"] = float(v)
        elif k == "S21.G00.51.011":
            code51 = v
        elif k == "S21.G00.51.013" and code51:
            out[nom]["51"][code51] = out[nom]["51"].get(code51, 0.0) + float(v)
        elif k == "S21.G00.58.003":
            type58 = v
        elif k == "S21.G00.58.004" and type58:
            out[nom]["58"][type58] = float(v)
    return out


dsn_path = RACINE_DATA / dossier_societe(company) / "dsn" / f"{year:04d}-{month:02d}.dsn"
refs = parse_dsn(dsn_path)
cid = resolve_company_id(company)
emps = (supabase.table("employees")
        .select("id, company_id, first_name, last_name, nom_usage, matricule, employee_folder_name, "
                "is_forfait_jour, hire_date, contract_end_date")
        .eq("company_id", cid).execute().data)
emps = [e for e in emps if _present_in_month(e, year, month)]

matched = []
for nom, ref in refs.items():
    cands = [e for e in emps if _normalize(e.get("last_name")) == _normalize(nom)
             or _normalize(e.get("nom_usage")) == _normalize(nom)
             or _normalize(e.get("matricule")) == _normalize(nom)]
    if len(cands) > 1 and ref.get("prenom"):
        cands = [e for e in cands if _normalize(e.get("first_name")) == _normalize(ref["prenom"])] or cands
    if not cands:
        print(f"[non apparié] {nom}"); continue
    e = cands[0]
    if wanted and e["matricule"] not in wanted:
        continue
    matched.append((EmployeeMatch(
        employee_id=e["id"], company_id=cid, matricule=e["matricule"], first_name=e.get("first_name") or "",
        last_name=e.get("last_name") or "", employee_folder_name=e.get("employee_folder_name") or "",
        is_forfait_jour=bool(e.get("is_forfait_jour")), reference=None), ref))

errs = []
if regen:
    def gen(item):
        m, _ = item
        try:
            _generate_payslip(m, year, month); return None
        except Exception as exc:  # noqa: BLE001
            return f"{m.matricule}: {exc}"
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(gen, matched):
            if r:
                errs.append(r)
for e in errs:
    print("[GENERR]", e)

rows = []
for m, ref in matched:
    data = _load_payslip_data(m.employee_id, year, month) or {}
    syn = data.get("synthese_net") or {}
    pas_e = (syn.get("impot_prelevement_a_la_source") or {}).get("montant")
    got = {
        "brut": data.get("salaire_brut"),
        "net_imposable": syn.get("net_imposable"),
        "mns": syn.get("montant_net_social"),
        "pas": pas_e,
    }
    exp = {
        "brut": ref["51"].get("001"),
        "net_imposable": ref.get("net_imposable"),
        "mns": ref["58"].get("03"),
        "pas": ref.get("pas"),
    }
    deltas = {}
    for k in ("brut", "net_imposable", "mns", "pas"):
        if got[k] is None or exp[k] is None:
            deltas[k] = None
        else:
            deltas[k] = round(float(got[k]) - float(exp[k]), 2)
    worst = max((abs(d) for d in deltas.values() if d is not None), default=999.0)
    rows.append((worst, m.matricule, got, exp, deltas))

rows.sort()
nconv = sum(1 for r in rows if r[0] <= 0.05)
print(f"\n=== {company} {year}-{month:02d} vs DSN : {nconv}/{len(rows)} convergés (≤0,05 sur brut/NI/MNS/PAS) ===")
for worst, mat, got, exp, deltas in rows:
    if worst <= 0.05:
        continue
    det = " ".join(f"{k}={d:+.2f}" for k, d in deltas.items() if d is not None and abs(d) > 0.05)
    manque = " ".join(f"{k}=?" for k, d in deltas.items() if d is None)
    print(f"  {mat:12s} {worst:9.2f}  {det} {manque}   (DSN brut={exp['brut']} NI={exp['net_imposable']} MNS={exp['mns']} PAS={exp['pas']})")
