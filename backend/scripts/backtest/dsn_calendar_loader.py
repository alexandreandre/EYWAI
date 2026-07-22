"""Loader DSN -> calendriers/inputs de paie (backtest).

Source = DSN (données déclarées réelles, distinctes du bulletin). Par salarié/mois :
  - HS conjoncturelles (rému code 017) -> monthly_inputs, split 25/50 déduit
    algébriquement du montant (taux structurel 018 = 25%, ×1.2 = 50%).
  - Absences : arrêts (bloc 60, motif+dates) + heures d'absence hors arrêt
    (activité 53 nature 02) -> jours du planned_calendar.

Idempotent : purge les lignes/jours marqués DSN_LOADER avant réinsertion.
NE lit JAMAIS les bulletins. NE vide PAS actual_hours sans raison.

Usage:
  python -m scripts.backtest.dsn_calendar_loader --company Colorplast --month 1 --dump
  python -m scripts.backtest.dsn_calendar_loader --company Colorplast --month 1 --apply
"""
from __future__ import annotations
import argparse, calendar as _cal, copy, re
from pathlib import Path
from datetime import date, timedelta

MARKER = "DSN_LOADER"

# DSN nom (S21.G00.30.002) -> matricule DB. Colorplast (9 salariés).
NOM_TO_MAT = {
    "BUGNY": "BUGNY", "CHALEYSSIN": "CHALEYSSIN", "COTTE": "COTTE",
    "DA SILVA CARDOSO": "DASILVACAR", "DEMORY": "DEMORY", "ESPINOSA": "ESPINOSA",
    "FUCKAR": "FUCKAR", "GAUTHERON": "GAUTHERON", "GIRERD": "GIRERD",
}

# Fichiers DSN par entreprise/mois (jan-mai ; juin = pointages, hors loader DSN).
DSN_FILES = {
    "Colorplast": {
        1: "Config/Colorplast/DSN/000005_0126_000001 (1).dsn",
        2: "Config/Colorplast/DSN/000005_0226_000001 (1).dsn",
        3: "Config/Colorplast/DSN/000005_0326_000001 (1).dsn",
        4: "Config/Colorplast/DSN/000005_0426_000001 (1).dsn",
        5: "Config/Colorplast/DSN/000005_0526_000001 (2).dsn",
    },
}

REPO = Path(__file__).resolve().parents[3]

# Motif arrêt DSN (60.001) -> (type EYWAI, libellé)
ARRET_MOTIF = {
    "01": ("arret_maladie", "Arrêt maladie"),
    "02": ("arret_maternite", "Maternité"),
    "03": ("arret_paternite", "Paternité"),
    "05": ("arret_at", "Accident du travail"),
    "06": ("arret_at", "Accident du travail/trajet"),
}


def _dsn_date(s: str) -> date | None:
    s = (s or "").strip()
    if not re.fullmatch(r"\d{8}", s):
        return None
    return date(int(s[4:8]), int(s[2:4]), int(s[0:2]))


def parse_dsn(path: Path) -> dict:
    """Retourne {matricule: {hs017:(h,montant), hs_struct_taux, arrets:[...],
    abs_hours_hors_arret: float}}."""
    lines = path.read_text(encoding="latin-1").splitlines()
    idx = [i for i, l in enumerate(lines) if l.startswith("S21.G00.30.002")]
    out = {}
    for k, s in enumerate(idx):
        e = idx[k + 1] if k + 1 < len(idx) else len(lines)
        b = lines[s:e]
        nom = b[0].split(",", 1)[1].strip("'")
        mat = NOM_TO_MAT.get(nom)
        if not mat:
            continue
        # rému 51 : collecter code 017 (conjoncturel) et 018 (structurel, pour le taux 25%)
        hs017 = None
        taux_struct = None
        for j, l in enumerate(b):
            if l.startswith("S21.G00.51.011"):
                code = l.split(",")[1].strip("'")
                h = m = None
                for l2 in b[j + 1:j + 6]:
                    if l2.startswith("S21.G00.51.012"):
                        h = l2.split(",")[1].strip("'")
                    elif l2.startswith("S21.G00.51.013"):
                        m = l2.split(",")[1].strip("'")
                    elif l2.startswith("S21.G00.51.011"):
                        break
                if code == "017" and h and m:
                    hs017 = (float(h), float(m))
                elif code == "018" and h and m and float(h):
                    taux_struct = float(m) / float(h)  # taux HS 25%
        # arrêts (bloc 60)
        arrets = []
        cur = None
        for l in b:
            mo = re.match(r"S21\.G00\.60\.(\d+),'([^']*)'", l)
            if mo:
                if mo.group(1) == "001":
                    if cur:
                        arrets.append(cur)
                    cur = {}
                if cur is not None:
                    cur[mo.group(1)] = mo.group(2)
        if cur:
            arrets.append(cur)
        # heures d'absence hors arrêt (activité 53 nature 02)
        abs_hours = 0.0
        cur_nat = None
        for l in b:
            if l.startswith("S21.G00.53.001"):
                cur_nat = l.split(",")[1].strip("'")
            elif l.startswith("S21.G00.53.002") and cur_nat == "02":
                abs_hours += float(l.split(",")[1].strip("'"))
        out[mat] = {"hs017": hs017, "taux_struct": taux_struct,
                    "arrets": arrets, "abs_hours_53": abs_hours}
    return out


def split_hs_25_50(hs_h: float, hs_montant: float, taux_25: float):
    """Résout (h25, h50) : h25*taux25 + h50*(taux25*1.2) = montant, h25+h50 = hs_h."""
    if not taux_25 or hs_h <= 0:
        return hs_h, 0.0
    taux_50 = taux_25 * 1.2
    # montant = h25*taux25 + (H-h25)*taux50  => h25 = (H*taux50 - montant)/(taux50-taux25)
    denom = taux_50 - taux_25
    if denom <= 0:
        return hs_h, 0.0
    h25 = (hs_h * taux_50 - hs_montant) / denom
    h25 = max(0.0, min(hs_h, round(h25, 2)))
    h50 = round(hs_h - h25, 2)
    return h25, h50


def arret_days(a: dict, year: int, month: int) -> list[int]:
    """Jours (numéros) d'absence du mois couverts par l'arrêt (dernier jour travaillé
    +1 -> fin d'arrêt 60.003, borné au mois)."""
    debut = _dsn_date(a.get("002"))  # dernier jour travaillé
    fin = _dsn_date(a.get("003"))    # fin de l'arrêt
    reprise = _dsn_date(a.get("010"))
    if fin is None and reprise:
        fin = reprise - timedelta(days=1)
    if debut is None or fin is None:
        return []
    d0 = debut + timedelta(days=1)
    days = []
    d = d0
    while d <= fin:
        if d.year == year and d.month == month:
            days.append(d.day)
        d += timedelta(days=1)
    return days


def build_records(company: str, month: int, year: int = 2026) -> dict:
    path = REPO / DSN_FILES[company][month]
    parsed = parse_dsn(path)
    recs = {}
    for mat, d in parsed.items():
        h25 = h50 = 0.0
        if d["hs017"]:
            h25, h50 = split_hs_25_50(d["hs017"][0], d["hs017"][1],
                                      d["taux_struct"] or 0.0)
        arret_abs = []  # (type, libelle, [jours])
        for a in d["arrets"]:
            motif = a.get("001")
            typ, lib = ARRET_MOTIF.get(motif, ("absence", f"Absence motif {motif}"))
            days = arret_days(a, year, month)
            if days:
                arret_abs.append((typ, lib, days, motif))
        recs[mat] = {"h25": h25, "h50": h50, "arrets": arret_abs,
                     "abs_hours_53": d["abs_hours_53"]}
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="Colorplast")
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    recs = build_records(a.company, a.month, a.year)
    if a.dump or not a.apply:
        print(f"=== {a.company} {a.month:02d}/{a.year} — extraction DSN ===")
        for mat in sorted(recs):
            r = recs[mat]
            arr = " ".join(f"{t}(m{mo}) j{days}" for t, l, days, mo in r["arrets"])
            print(f"  {mat:12} HS25={r['h25']:.2f} HS50={r['h50']:.2f} "
                  f"abs53={r['abs_hours_53']:.1f}h  {arr}")
        return
    if a.apply:
        from scripts.backtest.dsn_calendar_apply import apply_records
        apply_records(a.company, a.year, a.month, recs)


if __name__ == "__main__":
    main()
