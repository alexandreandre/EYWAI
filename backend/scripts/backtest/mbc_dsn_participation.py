"""Extrait le split participation numéraire/PEE de la DSN MBC mai 2026.

S21.G00.54.001='11' = participation TOTALE ; ='37' = part numéraire.
PEE = total - numéraire. Compare au monthly_input DB et signale les PEE manquants.

Usage: .venv/bin/python -m scripts.backtest.mbc_dsn_participation
"""
from __future__ import annotations
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.database import get_supabase_admin_client
from scripts.backtest.employee_matching import match_employees, resolve_company_id
from scripts.backtest.pdf_loader import load_reference_bulletins

DSN = "/Users/alex/Desktop/EYWAI/EYWAI/Config/MBC/DSN/000001_0526_000001 (1).dsn"
COMPANY = "Mont Blanc Composite"
YEAR, MONTH = 2026, 5


def parse_dsn():
    """Retourne {(nom_upper, prenom_upper): {'total':x, 'num':y}}."""
    text = Path(DSN).read_bytes().decode("iso-8859-1")
    out = {}
    nom = prenom = None
    cur = None
    pending_code = None
    for line in text.splitlines():
        m = re.match(r"S21\.G00\.30\.(\d{3}),'(.*)'", line)
        if m:
            f, v = m.group(1), m.group(2)
            if f == "002":  # nom de famille
                nom = v.strip().upper(); prenom = None
                cur = out.setdefault((nom, None), {"total": 0.0, "num": 0.0})
            elif f == "004":  # prénoms
                prenom = v.strip().split()[0].upper() if v.strip() else None
            continue
        m = re.match(r"S21\.G00\.54\.001,'(\d+)'", line)
        if m:
            pending_code = m.group(1); continue
        m = re.match(r"S21\.G00\.54\.002,'([-\d.]+)'", line)
        if m and pending_code in ("11", "37") and cur is not None:
            amt = float(m.group(1))
            if pending_code == "11":
                cur["total"] += amt
            else:
                cur["num"] += amt
            pending_code = None
    return out


def main():
    dsn = parse_dsn()
    admin = get_supabase_admin_client()
    refs = load_reference_bulletins(COMPANY, YEAR, MONTH)
    cid = resolve_company_id(COMPANY)
    matched = match_employees(cid, refs).matched
    print(f"{'MAT':14s} {'nomDSN':16s} total     num       PEE       inputDB(num/pee)")
    for m in matched:
        key = (m.last_name.strip().upper(), None)
        d = dsn.get(key)
        if not d or d["total"] <= 0:
            continue
        pee = round(d["total"] - d["num"], 2)
        mi = (admin.table("monthly_inputs").select("name,amount")
              .match({"employee_id": m.employee_id, "year": YEAR, "month": MONTH}).execute().data) or []
        num_db = next((r["amount"] for r in mi if "participation" in (r["name"] or "").lower()
                       and "pee" not in (r["name"] or "").lower() and "avance" not in (r["name"] or "").lower()
                       and (r["amount"] or 0) > 0), None)
        pee_db = next((r["amount"] for r in mi if "participation" in (r["name"] or "").lower()
                       and "pee" in (r["name"] or "").lower()), None)
        flag = ""
        if pee > 0.05 and not pee_db:
            flag = "  <<< PEE MANQUANT"
        print(f"{m.matricule:14s} {m.last_name[:16]:16s} {d['total']:9.2f} {d['num']:9.2f} {pee:9.2f}   {num_db}/{pee_db}{flag}")


if __name__ == "__main__":
    main()
