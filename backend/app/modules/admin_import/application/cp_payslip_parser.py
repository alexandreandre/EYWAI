"""Extraction des soldes CP depuis bulletins de paie PDF (Cegid clarifié, EYWAI)."""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, field
from typing import Literal, Optional

logger = logging.getLogger(__name__)

try:
    import pdfplumber

    _PDFPLUMBER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PDFPLUMBER_AVAILABLE = False

try:
    import PyPDF2

    _PYPDF2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYPDF2_AVAILABLE = False

ParseFormat = Literal["cegid_clarifie", "eywai_native", "unknown"]
MAX_PAGES_PER_FILE = 500

_FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

_CEGID_BULLETIN = re.compile(r"BULLETIN DE SALAIRE", re.IGNORECASE)
_EYWAI_SOLDE = re.compile(r"Solde de cong[eé]s au", re.IGNORECASE)


@dataclass
class ParsedPayslipPage:
    source_file: str
    page_index: int
    parse_format: ParseFormat = "unknown"
    company_name: Optional[str] = None
    siret: Optional[str] = None
    period_label: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    raw_name: Optional[str] = None
    matricule: Optional[str] = None
    cp_n1_solde: Optional[float] = None
    cp_n_solde: Optional[float] = None
    acquis_n1: Optional[float] = None
    acquis_n: Optional[float] = None
    pris_n1: Optional[float] = None
    pris_n: Optional[float] = None
    repos_cadre_days: Optional[int] = None
    parse_errors: list[str] = field(default_factory=list)

    @property
    def is_payslip_page(self) -> bool:
        return self.parse_format != "unknown" and self.cp_n1_solde is not None


def _normalize_month_token(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.strip().lower()


def parse_french_period(label: str) -> tuple[Optional[int], Optional[int], str]:
    """Parse « Mai 2026 » → (2026, 5, label)."""
    raw = (label or "").strip()
    match = re.match(r"^([A-Za-zÀ-ÿ]+)\s+(\d{4})$", raw)
    if not match:
        return None, None, raw
    month = _FRENCH_MONTHS.get(_normalize_month_token(match.group(1)))
    year = int(match.group(2))
    return year, month, raw


def _collapse_doubled_chars(text: str) -> str:
    """Corrige les PDF Cegid où pdfplumber duplique chaque caractère (BBUULL…)."""
    if not text or len(text) < 20:
        return text
    if "BULLETIN DE SALAIRE" in text.upper():
        return text
    sample = text[:600]
    pairs = sum(
        1 for i in range(0, min(len(sample) - 1, 598), 2) if sample[i] == sample[i + 1]
    )
    total_pairs = min(len(sample), 598) // 2
    if total_pairs == 0 or pairs / total_pairs < 0.65:
        return text
    out: list[str] = []
    i = 0
    while i < len(text):
        out.append(text[i])
        if i + 1 < len(text) and text[i] == text[i + 1]:
            i += 2
        else:
            i += 1
    return "".join(out)


def _normalize_page_text(text: str) -> str:
    return _collapse_doubled_chars(text)


def _parse_float_pair(pattern: str, text: str) -> tuple[Optional[float], Optional[float]]:
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _parse_cegid_clarifie(page_text: str) -> ParsedPayslipPage:
    page = ParsedPayslipPage(source_file="", page_index=0, parse_format="cegid_clarifie")

    company_match = re.search(
        r"^\s{0,5}([A-Z0-9][A-Z0-9 \.\-]{2,50}?)\s+BULLETIN DE SALAIRE",
        page_text,
        re.MULTILINE,
    )
    if company_match:
        page.company_name = company_match.group(1).strip()

    siret_match = re.search(r"Siret\s*:\s*(\d{14})", page_text, re.IGNORECASE)
    if siret_match:
        page.siret = siret_match.group(1)

    period_match = re.search(r"Période\s*:\s*([^\n]+)", page_text, re.IGNORECASE)
    if period_match:
        page.period_label = period_match.group(1).strip()
        page.year, page.month, page.period_label = parse_french_period(page.period_label)

    page.acquis_n1, page.acquis_n = _parse_float_pair(
        r"Acquis\s*:\s*([\d.]+)\s*/\s*([\d.]+)", page_text
    )
    page.pris_n1, page.pris_n = _parse_float_pair(
        r"Total pris\s*:\s*([\d.]+)\s*/\s*([\d.]+)", page_text
    )
    page.cp_n1_solde, page.cp_n_solde = _parse_float_pair(
        r"Solde\s*:\s*([\d.]+)\s*/\s*([\d.]+)", page_text
    )

    name_match = re.search(
        r"(?:Mr|M\.|Mme|Me)\s+([^\n]{2,80})",
        page_text,
    )
    if name_match:
        page.raw_name = name_match.group(1).strip()

    matricule_match = re.search(
        r"Matricule\s*:\s*(.+?)\s+NoS[eé]cu",
        page_text,
        re.IGNORECASE,
    )
    if matricule_match:
        page.matricule = matricule_match.group(1).strip()

    repos_match = re.search(
        r"Solde repos Cadre\s*=\s*(\d+)\s*j?",
        page_text,
        re.IGNORECASE,
    )
    if repos_match:
        page.repos_cadre_days = int(repos_match.group(1))

    if page.cp_n1_solde is None or page.cp_n_solde is None:
        page.parse_errors.append("Bloc CP N-1 / N introuvable sur la page.")
    if not page.siret:
        page.parse_errors.append("SIRET entreprise introuvable.")
    if not page.raw_name and not page.matricule:
        page.parse_errors.append("Identité salarié introuvable.")

    return page


def _parse_eywai_native(page_text: str) -> ParsedPayslipPage:
    page = ParsedPayslipPage(source_file="", page_index=0, parse_format="eywai_native")

    date_ref = re.search(
        r"Solde de cong[eé]s au\s+(\d{2}/\d{2}/(\d{4}))",
        page_text,
        re.IGNORECASE,
    )
    if date_ref:
        page.period_label = date_ref.group(1)
        page.year = int(date_ref.group(2))
        parts = date_ref.group(1).split("/")
        if len(parts) == 3:
            page.month = int(parts[1])

    prev_block = re.search(
        r"CP p[eé]riode pr[eé]c[eé]dente.*?([\d.]+)\s*j.*?([\d.]+)\s*j.*?([\d.]+)\s*j",
        page_text,
        re.DOTALL | re.IGNORECASE,
    )
    current_block = re.search(
        r"CP p[eé]riode en cours.*?([\d.]+)\s*j.*?([\d.]+)\s*j.*?([\d.]+)\s*j",
        page_text,
        re.DOTALL | re.IGNORECASE,
    )
    if prev_block:
        page.acquis_n1 = float(prev_block.group(1))
        page.pris_n1 = float(prev_block.group(2))
        page.cp_n1_solde = float(prev_block.group(3))
    else:
        page.cp_n1_solde = 0.0

    if current_block:
        page.acquis_n = float(current_block.group(1))
        page.pris_n = float(current_block.group(2))
        page.cp_n_solde = float(current_block.group(3))
    else:
        page.cp_n_solde = None

    name_match = re.search(
        r"class=\"employee-name\"[^>]*>([^<]+)|employee-name[^>]*>\s*([^<\n]+)",
        page_text,
        re.IGNORECASE,
    )
    if name_match:
        page.raw_name = (name_match.group(1) or name_match.group(2) or "").strip()

    siret_match = re.search(r"SIRET\s*:\s*(\d{14})", page_text, re.IGNORECASE)
    if siret_match:
        page.siret = siret_match.group(1)

    if page.cp_n_solde is None:
        page.parse_errors.append("Soldes CP EYWAI introuvables sur la page.")

    return page


def parse_payslip_page_text(page_text: str) -> ParsedPayslipPage:
    """Détecte le format et extrait les soldes CP d'une page bulletin."""
    page_text = _normalize_page_text(page_text)
    if _CEGID_BULLETIN.search(page_text) and re.search(
        r"CP\s+N-1", page_text, re.IGNORECASE
    ):
        return _parse_cegid_clarifie(page_text)
    if _EYWAI_SOLDE.search(page_text):
        return _parse_eywai_native(page_text)
    return ParsedPayslipPage(
        source_file="",
        page_index=0,
        parse_format="unknown",
        parse_errors=["Page non reconnue comme bulletin de paie."],
    )


def _extract_with_pdftotext(content: bytes, max_pages: int) -> tuple[list[str], list[str]]:
    """Extraction via pdftotext (meilleure qualité sur bulletins Cegid)."""
    warnings: list[str] = []
    if not shutil.which("pdftotext"):
        return [], warnings
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        proc = subprocess.run(
            ["pdftotext", "-layout", tmp_path, "-"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            warnings.append("pdftotext n'a pas pu lire le PDF.")
            return [], warnings
        pages_raw = proc.stdout.split("\f")
        pages = [
            _normalize_page_text(p)
            for p in pages_raw
            if p.strip()
        ]
        if len(pages) > max_pages:
            warnings.append(
                f"PDF tronqué à {max_pages} pages sur {len(pages)}."
            )
            pages = pages[:max_pages]
        return pages, warnings
    except Exception as exc:
        logger.warning("pdftotext extraction échouée: %s", exc)
        warnings.append("Extraction pdftotext en échec.")
        return [], warnings
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def extract_pdf_pages(content: bytes, *, max_pages: int = MAX_PAGES_PER_FILE) -> tuple[list[str], list[str]]:
    """Extrait le texte page par page. Retourne (pages, warnings)."""
    warnings: list[str] = []
    pages: list[str] = []

    pdftotext_pages, pdftotext_warnings = _extract_with_pdftotext(content, max_pages)
    warnings.extend(pdftotext_warnings)
    if pdftotext_pages:
        return pdftotext_pages, warnings

    if _PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                total = len(pdf.pages)
                if total > max_pages:
                    warnings.append(
                        f"PDF tronqué à {max_pages} pages sur {total}."
                    )
                for page in pdf.pages[:max_pages]:
                    pages.append(_normalize_page_text(page.extract_text() or ""))
            if pages:
                return pages, warnings
        except Exception as exc:
            logger.warning("pdfplumber extraction échouée: %s", exc)
            warnings.append("Extraction pdfplumber en échec, repli PyPDF2.")

    if _PYPDF2_AVAILABLE:
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            total = len(reader.pages)
            if total > max_pages:
                warnings.append(
                    f"PDF tronqué à {max_pages} pages sur {total}."
                )
            for page in reader.pages[:max_pages]:
                pages.append(_normalize_page_text(page.extract_text() or ""))
        except Exception as exc:
            logger.warning("PyPDF2 extraction échouée: %s", exc)
            raise ValueError("Impossible de lire le PDF.") from exc

    if not pages:
        raise ValueError("Impossible de lire le PDF (aucune bibliothèque disponible).")

    return pages, warnings


def parse_pdf_file(
    filename: str,
    content: bytes,
    *,
    max_pages: int = MAX_PAGES_PER_FILE,
) -> tuple[list[ParsedPayslipPage], list[str]]:
    """Parse un fichier PDF bulletin et retourne les pages reconnues."""
    file_warnings: list[str] = []
    try:
        pages, extract_warnings = extract_pdf_pages(content, max_pages=max_pages)
    except ValueError as exc:
        return [], [str(exc)]

    file_warnings.extend(extract_warnings)
    results: list[ParsedPayslipPage] = []

    for idx, page_text in enumerate(pages):
        if not page_text.strip():
            continue
        if not (_CEGID_BULLETIN.search(page_text) or _EYWAI_SOLDE.search(page_text)):
            continue
        parsed = parse_payslip_page_text(page_text)
        parsed.source_file = filename
        parsed.page_index = idx + 1
        if parsed.is_payslip_page or parsed.parse_format != "unknown":
            results.append(parsed)

    if not results and not file_warnings:
        file_warnings.append("Aucun bulletin de paie reconnu dans le fichier.")

    return results, file_warnings
