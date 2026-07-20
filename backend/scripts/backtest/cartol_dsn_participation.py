"""Parse participation Cartol depuis DSN (vérité centime), clé = matricule (=30.002).

S21.G00.54.001='11' total ; ='37' numéraire. PEE = total - numéraire.
Merge dans scratchpad/cartol_extract_<MM>.json : participation (num) + participation_pee.

Usage: .venv/bin/python -m scripts.backtest.cartol_dsn_participation --month 5
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

SC = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad")
DSN_DIR = Path("/Users/alex/Desktop/EYWAI/EYWAI/Config/Cartol/DSN")


def parse(month: int):
    f = next((p for p in DSN_DIR.glob("*.dsn") if f"_{month:02d}26_" in p.name), None)
    if not f:
        return {}
    text = f.read_bytes().decode("iso-8859-1")
    res, mat, pend = {}, None, None
    for line in text.splitlines():
        m = re.match(r"S21\.G00\.30\.002,'(.*)'", line)
        if m:
            mat = m.group(1).strip().upper()
            res.setdefault(mat, {"11": 0.0, "37": 0.0})
            continue
        m = re.match(r"S21\.G00\.54\.001,'(\d+)'", line)
        if m:
            pend = m.group(1); continue
        m = re.match(r"S21\.G00\.54\.002,'([-\d.]+)'", line)
        if m and pend in ("11", "37") and mat:
            res[mat][pend] += float(m.group(1)); pend = None
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, default=5)
    a = ap.parse_args()
    part = parse(a.month)
    ext_path = SC / f"cartol_extract_{a.month:02d}.json"
    ext = json.loads(ext_path.read_text())
    n_num = n_pee = 0
    for mat, p in part.items():
        total, num = round(p["11"], 2), round(p["37"], 2)
        pee = round(total - num, 2)
        if mat not in ext:
            continue
        if total > 0:
            ext[mat]["participation"] = num       # numéraire (vérité DSN)
            n_num += 1
            if pee > 0.05:
                ext[mat]["participation_pee"] = pee
                n_pee += 1
    ext_path.write_text(json.dumps(ext, ensure_ascii=False, indent=1))
    print(f"DSN participation merged: {n_num} numéraire, {n_pee} avec PEE")


if __name__ == "__main__":
    main()
