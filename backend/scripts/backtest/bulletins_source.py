"""Résolveur générique pour le dossier `Bulletins/` (bulletins réels + pointages
janvier-juin 2026, 5 entreprises : Colorplast, MBC, Lewis, Cartol, Comitech).

Structure attendue (détectée automatiquement, pas de config manuelle par
entreprise) :

    Bulletins/
      BULLETIN <NOM> 01 02 03 04 05 06/
        01/  <bulletin-du-mois>.pdf  + fichiers pointage (xlsx/pdf)
        02/  ...
        ...
        06/  ...
      (Lewis fait exception : mois 01-05 = PDF bulletin directement à la
       racine du dossier entreprise, pas de sous-dossier mensuel ; seul le
       mois 06 a un sous-dossier avec bulletin + pointage + calendrier.)

Usage typique (remplace la construction de chemin manuelle utilisée pendant
la session du 12/07) :

    from scripts.backtest.bulletins_source import resolve_bulletin_pdf, list_pointage_files
    pdf = resolve_bulletin_pdf("Lewis", 2026, 6)
    refs = load_reference_bulletins("Lewis", 2026, 6, pdf_path=pdf)
    pointages = list_pointage_files("Lewis", 2026, 6)   # xlsx/pdf de pointage/calendrier

Pour lister tout ce qui est backtestable dans le dossier :

    .venv/bin/python -m scripts.backtest.bulletins_source --list

Pour lancer un backtest complet entreprise/mois quelconque de ce dossier :

    .venv/bin/python -m scripts.backtest.bulletins_source --backtest Cartol 2026 5
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

BULLETINS_ROOT = Path("/Users/alex/Desktop/EYWAI/EYWAI/Bulletins")

# Alias -> nom EXACT du dossier "BULLETIN <NOM> 01 02 03 04 05 06" (sans le
# préfixe "BULLETIN " ni le suffixe des mois, reconstruit dynamiquement).
COMPANY_DIR_ALIASES: Dict[str, str] = {
    "colorplast": "COLORPLAST",
    "cartol": "CARTOL",
    "comitech": "COMITECH",
    "comitech composite": "COMITECH",
    "lewis": "LEWIS",
    "mbc": "MBC",
    "mont blanc composite": "MBC",
}

_BULLETIN_NAME_HINTS = ("bulletin", "salaire")
_POINTAGE_NAME_HINTS = ("pointage", "semaine", "s0", "s1", "s2", "calendrier")


def resolve_company_root(company_name: str) -> Path:
    key = company_name.strip().lower()
    folder_key = COMPANY_DIR_ALIASES.get(key, company_name.upper())
    candidates = list(BULLETINS_ROOT.glob(f"BULLETIN {folder_key}*"))
    if not candidates:
        raise FileNotFoundError(
            f"Aucun dossier 'BULLETIN {folder_key}*' dans {BULLETINS_ROOT}"
        )
    return candidates[0]


def _month_dir(company_root: Path, month: int) -> Optional[Path]:
    d = company_root / f"{month:02d}"
    return d if d.is_dir() else None


def _looks_like_bulletin(path: Path, month: int, year: int) -> bool:
    """True si `path` est le bulletin de paie du mois/année demandés (et pas
    un pointage). Le nom doit soit contenir un mot-clé bulletin ET être dans
    le bon dossier mensuel, soit porter explicitement le motif MM-YY/MM-YYYY
    du mois demandé (cas Lewis : PDF à la racine, un par mois)."""
    name = path.stem.lower()
    if any(h in name for h in _POINTAGE_NAME_HINTS):
        return False
    has_bulletin_hint = any(h in name for h in _BULLETIN_NAME_HINTS)
    yy = str(year)[2:]
    month_tag_yy = f"{month:02d}-{yy}"
    month_tag_yyyy = f"{month:02d}-{year}"
    has_month_tag = name.startswith(month_tag_yy) or name.startswith(month_tag_yyyy)
    if has_bulletin_hint or has_month_tag:
        return True
    return False


def resolve_bulletin_pdf(company_name: str, year: int, month: int) -> Path:
    """Retourne le chemin du PDF bulletin de paie réel pour company/year/month,
    quelle que soit la convention de nommage utilisée par ce mois/entreprise."""
    root = resolve_company_root(company_name)
    mdir = _month_dir(root, month)
    search_dirs = [mdir] if mdir else [root]
    for d in search_dirs:
        pdfs = sorted(p for p in d.glob("*.pdf"))
        bulletin_candidates = [p for p in pdfs if _looks_like_bulletin(p, month, year)]
        if bulletin_candidates:
            return bulletin_candidates[0]
        if pdfs and not mdir:
            # Cas Lewis mois 01-05 : PDF direct à la racine nommé "MM-YY LEWIS.pdf"
            month_str = f"{month:02d}-{str(year)[2:]}"
            for p in pdfs:
                if p.stem.lower().startswith(month_str):
                    return p
    raise FileNotFoundError(
        f"Aucun bulletin PDF trouvé pour {company_name} {year}-{month:02d} "
        f"(cherché dans {mdir or root})"
    )


def list_pointage_files(company_name: str, year: int, month: int) -> List[Path]:
    """Liste tous les fichiers de pointage/calendrier (xlsx/pdf, hors bulletin
    principal) disponibles pour company/year/month — y compris les
    sous-dossiers du type 'POINTAGE 05-2026/' (Lewis)."""
    root = resolve_company_root(company_name)
    mdir = _month_dir(root, month)
    bulletin = resolve_bulletin_pdf(company_name, year, month)
    out: List[Path] = []

    if mdir:
        # Sous-dossier mensuel classique : tout ce qui n'est pas le bulletin.
        for p in mdir.rglob("*"):
            if p.is_dir() or p == bulletin:
                continue
            if p.suffix.lower() not in (".xlsx", ".pdf", ".xls"):
                continue
            out.append(p)
    else:
        # Cas Lewis mois 01-05 : pas de sous-dossier, les fichiers pointage
        # sont soit à la racine avec le motif "POINTAGE MM-YYYY.xlsx", soit
        # dans un sous-dossier dédié "POINTAGE MM-YYYY/" (jamais rglob sur
        # tout `root`, sinon on récupère aussi les autres mois).
        month_tag = f"{month:02d}-{year}"
        for p in root.glob("*.xlsx"):
            if month_tag in p.stem:
                out.append(p)
        for d in root.glob(f"POINTAGE {month_tag}*"):
            if d.is_dir():
                out.extend(x for x in d.glob("*") if x.is_file())

    return sorted(set(out))


def list_available(company_name: Optional[str] = None) -> Dict[str, List[int]]:
    """Renvoie {entreprise: [mois disponibles]} pour tout le dossier Bulletins,
    ou une seule entreprise si précisé."""
    result: Dict[str, List[int]] = {}
    companies = (
        [company_name] if company_name else list(dict.fromkeys(COMPANY_DIR_ALIASES.values()))
    )
    for c in companies:
        months = []
        for m in range(1, 13):
            try:
                resolve_bulletin_pdf(c, 2026, m)
                months.append(m)
            except FileNotFoundError:
                continue
        if months:
            result[c] = months
    return result


def _cli():
    args = sys.argv[1:]
    if "--list" in args:
        for company, months in list_available().items():
            print(f"{company}: mois {months}")
        return
    if "--backtest" in args:
        i = args.index("--backtest")
        company, year, month = args[i + 1], int(args[i + 2]), int(args[i + 3])
        pdf = resolve_bulletin_pdf(company, year, month)
        pointages = list_pointage_files(company, year, month)
        print(f"Bulletin : {pdf}")
        print(f"Pointages ({len(pointages)}) :")
        for p in pointages:
            print(f"  - {p}")
        print()
        print("Pour lancer le backtest complet, utiliser ce PDF en pdf_path :")
        print(
            "  from scripts.backtest.pdf_loader import load_reference_bulletins\n"
            f"  refs = load_reference_bulletins({company!r}, {year}, {month}, "
            f"pdf_path=Path({str(pdf)!r}))"
        )
        return
    print(__doc__)


if __name__ == "__main__":
    _cli()
