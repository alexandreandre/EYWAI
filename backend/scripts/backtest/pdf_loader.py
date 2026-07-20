"""Chargement PDF Cegid depuis Config/<Entreprise>/Compteur CP."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Optional

from app.modules.payroll.backtest.models import ReferenceBulletin
from app.modules.payroll.backtest.reference_parser import parse_cegid_text

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "Config"

COMPANY_FOLDER_ALIASES: Dict[str, str] = {
    "colorplast": "Colorplast",
    "cartol": "Cartol",
    "comitech": "Comitech Composite",
    "comitech composite": "Comitech Composite",
    "lewis": "Lewis",
    "mbc": "MBC",
    "mont blanc composite": "MBC",
    "maji": "Maji",
    "zone": "Zone",
    "exemple": "Exemple",
}


def resolve_company_folder(company_name: str) -> Path:
    key = company_name.strip().lower()
    folder = COMPANY_FOLDER_ALIASES.get(key, company_name)
    path = CONFIG_ROOT / folder
    if not path.exists():
        raise FileNotFoundError(f"Dossier Config introuvable pour '{company_name}': {path}")
    return path


def find_reference_pdf(company_name: str, year: int, month: int) -> Path:
    company_dir = resolve_company_folder(company_name)
    cp_dirs = list(company_dir.glob("Compteur CP*"))
    if not cp_dirs:
        raise FileNotFoundError(f"Aucun dossier Compteur CP dans {company_dir}")
    cp_dir = cp_dirs[0]
    month_str = f"{month:02d}-{year}"
    pdfs = sorted(cp_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"Aucun PDF dans {cp_dir}")
    # Préférer le PDF contenant le mois-année
    for pdf in pdfs:
        if month_str in pdf.name or f"{month:02d}" in pdf.name:
            return pdf
    return pdfs[0]


def extract_pdf_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def load_reference_bulletins(
    company_name: str,
    year: int,
    month: int,
    *,
    pdf_path: Path | None = None,
) -> Dict[str, ReferenceBulletin]:
    pdf = pdf_path or find_reference_pdf(company_name, year, month)
    text = extract_pdf_text(pdf)
    return parse_cegid_text(text)
