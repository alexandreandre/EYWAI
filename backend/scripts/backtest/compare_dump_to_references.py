"""Compare un relevé de bulletins (sortie de `scripts/dump_payslips_test.py`,
journal de workflow accepté tel quel) aux références du cabinet :
bulletins Cegid (`data/<societe>/bulletins/<AAAA-MM>/md/<MAT>.md`, produits par
`export_reference_md`) puis, à défaut, DSN (`data/<societe>/dsn/<AAAA-MM>.dsn`).

Critère tier S : brut, net imposable, MNS, net à payer (bulletin) ou brut, net
imposable, MNS, PAS (DSN) tous à ≤ 0,05 €.

Usage :
    python -m scripts.backtest.compare_dump_to_references <releve.txt> [--company Maji] [--month 6]
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backtest.pdf_loader import RACINE_DATA, dossier_societe  # noqa: E402

ALIAS_DSN = {"KEWITZ": "BOUALI", "ROZIER": "PELLET", "VERNY": "VERNYC", "AGOUMBI OGANDAGA": "AGOUMBI"}
SEUIL = 0.05


def refs_md(dossier: str, year: int, month: int) -> dict:
    out = {}
    for f in glob.glob(str(RACINE_DATA / dossier / "bulletins" / f"{year}-{month:02d}" / "md" / "*.md")):
        mat = Path(f).stem
        if mat == "README":
            continue
        txt = Path(f).read_text(encoding="utf-8")

        def g(label: str):
            r = re.search(r"\| \**" + re.escape(label) + r"\** \| \**([\d ,.\-]+) €", txt)
            return float(r.group(1).replace(" ", "").replace(",", ".")) if r else None

        out[mat] = {"brut": g("Salaire brut"), "net_imposable": g("Net imposable"),
                    "mns": g("Montant net social (MNS)"), "net_a_payer": g("Net à payer"), "pas": g("Montant PAS")}
    return out


def refs_dsn(dossier: str, year: int, month: int) -> dict:
    path = RACINE_DATA / dossier / "dsn" / f"{year}-{month:02d}.dsn"
    if not path.exists():
        return {}
    out: dict = {}
    nom = None; c51 = None; t58 = None
    for line in open(path, encoding="iso-8859-1"):
        k, _, v = line.strip().partition(","); v = v.strip("'")
        if k == "S21.G00.30.002":
            nom = v; out[nom] = {}
        elif nom is None:
            continue
        elif k == "S21.G00.50.002":
            out[nom]["net_imposable"] = float(v)
        elif k == "S21.G00.50.009":
            out[nom]["pas"] = float(v)
        elif k == "S21.G00.51.011":
            c51 = v
        elif k == "S21.G00.51.013" and c51 == "001":
            out[nom]["brut"] = out[nom].get("brut", 0.0) + float(v)
        elif k == "S21.G00.58.003":
            t58 = v
        elif k == "S21.G00.58.004" and t58 == "03":
            out[nom]["mns"] = float(v)
    return {ALIAS_DSN.get(k, k): v for k, v in out.items()}


def lire_releve(path: Path) -> dict:
    releve: dict = {}
    inside = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = re.sub(r"^.*\t", "", raw.strip())     # préfixe « job\tstep\t » du journal GitHub
        line = re.sub(r"^\S*Z\s", "", line)          # puis l'horodatage
        if line == "DUMP_BEGIN":
            inside = True; continue
        if line == "DUMP_END":
            break
        if not inside or line.startswith("societe;"):
            continue
        parts = line.split(";")
        if len(parts) != 10:
            continue
        soc, mat, year, month, statut, *vals = parts
        f = lambda s: float(s) if s not in ("", "None") else None  # noqa: E731
        releve.setdefault((soc, int(year), int(month)), {})[mat] = {
            "statut": statut, "brut": f(vals[0]), "net_imposable": f(vals[1]), "mns": f(vals[2]),
            "net_a_payer": f(vals[3]), "pas": f(vals[4])}
    return releve


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("releve")
    ap.add_argument("--company")
    ap.add_argument("--month", type=int)
    args = ap.parse_args()
    releve = lire_releve(Path(args.releve))
    if not releve:
        raise SystemExit("Aucune ligne de relevé trouvée (bloc DUMP_BEGIN … DUMP_END attendu).")
    for (soc, year, month), rows in sorted(releve.items()):
        if args.company and args.company.lower() not in soc.lower():
            continue
        if args.month and month != args.month:
            continue
        dossier = dossier_societe(soc)
        refs = refs_md(dossier, year, month)
        source = "bulletins"
        if not refs:
            refs = refs_dsn(dossier, year, month)
            source = "DSN"
        if not refs:
            print(f"{soc} {month:02d}/{year} : pas de référence (ni md ni DSN) — {len(rows)} bulletins relevés")
            continue
        keys = ("brut", "net_imposable", "mns", "net_a_payer", "pas") if source == "bulletins" else ("brut", "net_imposable", "mns", "pas")
        conv = 0; total = 0; details = []
        for mat, ref in sorted(refs.items()):
            e = rows.get(mat)
            if not e:
                details.append(f"{mat}: pas de bulletin"); continue
            total += 1
            deltas = {k: e[k] - ref[k] for k in keys if e.get(k) is not None and ref.get(k) is not None}
            worst = max((abs(d) for d in deltas.values()), default=999.0)
            if worst <= SEUIL:
                conv += 1
            else:
                details.append(f"{mat} {worst:.2f} (" + " ".join(f"{k}={d:+.2f}" for k, d in deltas.items() if abs(d) > SEUIL) + ")")
        en_trop = sorted(set(rows) - set(refs))
        print(f"{soc} {month:02d}/{year} vs {source} : {conv}/{total} exacts"
              + (" — " + " ; ".join(details) if details else "")
              + (f" — sans référence : {', '.join(en_trop)}" if en_trop else ""))


if __name__ == "__main__":
    main()
