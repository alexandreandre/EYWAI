"""Extrait les données mensuelles Cartol depuis les bulletins_md réels (raw text).

Produit scratchpad/cartol_extract_<MM>.json : par matricule, les éléments
nécessaires à la reconciliation (ancre documentaire réelle, jamais inventée).

Usage: .venv/bin/python -m scripts.backtest.cartol_extract --month 5
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

MD_DIR_TPL = ("/Users/alex/Desktop/EYWAI/EYWAI/Config/Cartol/"
              "Compteur CP (bulletins de mai)/bulletins_md_{year}-{month:02d}")
SC = Path("/private/tmp/claude-501/-Users-alex-Desktop-EYWAI-EYWAI/"
          "cfdb3f75-b90e-430f-922f-effaf4ea2dbd/scratchpad")


def _raw(md_text: str) -> str:
    m = re.search(r"```(.*)```", md_text, re.S)
    return m.group(1) if m else md_text


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _days_range(d1: str, d2: str):
    a, b = int(d1[:2]), int(d2[:2])
    return list(range(a, b + 1)) if a <= b else [a]


def parse_one(raw: str) -> dict:
    out = {}
    m = re.search(r"Ancienn\S*\s*:\s*(\d{2}/\d{2}/\d{4})", raw)
    if m:
        dd, mm, yy = m.group(1).split("/")
        out["anciennete"] = f"{yy}-{mm}-{dd}"
    m = re.search(r"Entr\S*\)? le :\s*(\d{2}/\d{2}/\d{4})", raw)
    if m:
        dd, mm, yy = m.group(1).split("/")
        out["hire"] = f"{yy}-{mm}-{dd}"
    m = re.search(r"Coeff:\s*(\S+)", raw)
    if m:
        out["coeff"] = m.group(1)
    m = re.search(r"SALAIRE DE BASE\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", raw)
    if m:
        out["base_h"], out["base_rate"], out["base_amt"] = _f(m[1]), _f(m[2]), _f(m[3])
    m = re.search(r"PRIME ANCIENNETE\s+([\d.]+)\s+([\d.]+)", raw)
    if m:
        out["prime_anc"] = _f(m[2])
    # Participation: line "Participation 2025    <base>    ... <montant>"
    m = re.search(r"Participation 20\d\d\s+([\d.]+)\s+([\d.]+)", raw)
    if m:
        out["participation"] = _f(m[2])
    else:
        m = re.search(r"Participation 20\d\d\s+([\d.]+)", raw)
        if m:
            out["participation"] = _f(m[1])
    m = re.search(r"Acompte Participation 20\d\d\s+([\d.]+)", raw)
    if m:
        out["acompte_participation"] = _f(m[1])
    # CP ranges + count
    cp_days = []
    for d1, d2 in re.findall(r"Cong\S*s pay\S*s : (\d{6})-(\d{6})", raw):
        cp_days += _days_range(d1, d2)
    for d1 in re.findall(r"Cong\S*s pay\S*s : (\d{6})(?!-)", raw):
        cp_days.append(int(d1[:2]))
    out["cp_days"] = sorted(set(cp_days))
    mh = re.search(r"H\.Absence Cong\S*s Pay\S*s\s+([\d.]+)", raw)
    if mh:
        out["cp_hours"] = _f(mh[1])
    # JF non payé dates
    jf = sorted({int(x[:2]) for x in re.findall(r"Abs\. JF non pay\S* (\d{6})", raw)})
    out["jf_non_paye_days"] = jf
    # HS 25 / 50 (hours in base column)
    m = re.search(r"Heures suppl\S*mentaires 25\s+([\d.]+)", raw)
    if m:
        out["hs25_h"] = _f(m[1])
    m = re.search(r"Heures suppl\S*mentaires 50\s+([\d.]+)", raw)
    if m:
        out["hs50_h"] = _f(m[1])
    # Prevoyance line
    m = re.search(r"(EP\d) PREV GROUPAMA (NC|CADRE) T([AB])\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s+([\d.]+))?", raw)
    if m:
        out["prev"] = {"line": m[1], "statut": m[2], "tranche": m[3],
                       "base": _f(m[4]), "rate": _f(m[5]), "sal": _f(m[6]),
                       "pat": _f(m[7]) if m[7] else _f(m[6])}
    # Mutuelle line (ISOLE / ISOLE+ENFANT(S) / COUPLE / FAMILLE)
    m = re.search(r"EMU\d\s+(MUTUELLE[A-Z0-9 +()'S\-]*?)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", raw)
    if m:
        out["mut"] = {"label": m[1].strip(), "sal": _f(m[4]), "pat": _f(m[5])}
    # Note de frais / transport / acompte generic
    m = re.search(r"REMBOURSEMENT NOTE DE FRAIS\s+([\d.]+)", raw)
    if m:
        out["note_frais"] = _f(m[1])
    # Absences maladie / non rémunérées
    out["has_maladie"] = bool(re.search(r"maladie|Maladie|arr\S*t", raw))
    # PAS
    m = re.search(r"Imp\S*t sur le revenu pr\S*lev\S* \S* la source\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", raw)
    if m:
        out["pas_taux"], out["pas_montant"] = _f(m[2]), _f(m[3])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, default=5)
    ap.add_argument("--year", type=int, default=2026)
    a = ap.parse_args()
    md_dir = Path(MD_DIR_TPL.format(year=a.year, month=a.month))
    res = {}
    for f in sorted(md_dir.glob("*.md")):
        if f.name == "README.md":
            continue
        raw = _raw(f.read_text())
        mat = f.stem
        res[mat] = parse_one(raw)
    (SC / f"cartol_extract_{a.month:02d}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"extract -> {len(res)} salariés")
    # quick stats
    for k in ["prime_anc", "participation", "acompte_participation", "prev", "mut"]:
        n = sum(1 for v in res.values() if v.get(k) is not None)
        print(f"  {k}: {n}")
    n_jf = sum(1 for v in res.values() if v.get("jf_non_paye_days"))
    n_cp = sum(1 for v in res.values() if v.get("cp_days"))
    n_hs = sum(1 for v in res.values() if v.get("hs25_h") or v.get("hs50_h"))
    print(f"  jf_non_paye:{n_jf} cp:{n_cp} hs:{n_hs}")


if __name__ == "__main__":
    main()
