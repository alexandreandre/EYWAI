"""Parse le texte extrait d'un bulletin Cegid (pdftotext -layout)."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.modules.payroll.backtest.models import ReferenceBulletin, ReferenceRubricLine

_MATRICULE_RE = re.compile(
    r"Matricule\s*:\s*(.+?)\s{2,}NoS[ée]cu", re.IGNORECASE
)
_NIR_RE = re.compile(r"NoS[ée]cu\.?\s*:\s*(\d+)", re.IGNORECASE)
_NOM_RE = re.compile(
    r"M(?:R|me?)?\.?\s+([A-ZÀ-ÖØ-Ý][A-Za-zÀ-öø-ÿ\-']+(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-öø-ÿ\-']+)*)"
)
_COEFF_RE = re.compile(r"Coeff:\s*(\d+)")
_CP_SOLDE_RE = re.compile(r"Solde\s*:\s*[\d.,]+\s*/\s*([\d.,]+)\s*/")
_PAIEMENT_RE = re.compile(r"Paiement le\s*:\s*([\d/]+)")
_FLOAT_RE = r"([\d\s]+[.,]\d{2,4}|\d+)"
_BRUT_RE = re.compile(rf"SALAIRE BRUT\s+{_FLOAT_RE}", re.IGNORECASE)
_NET_IMP_RE = re.compile(rf"NET IMPOSABLE\s+{_FLOAT_RE}", re.IGNORECASE)
_MNS_RE = re.compile(rf"MONTANT NET SOCIAL\s+{_FLOAT_RE}", re.IGNORECASE)
_NET_AVANT_RE = re.compile(
    rf"NET A PAYER AVANT IMPOT SUR LE REVENU\s+{_FLOAT_RE}", re.IGNORECASE
)
_PAS_RE = re.compile(
    r"Imp[oô]t sur le revenu pr[eé]lev[eé] [àa] la source\s+"
    rf"{_FLOAT_RE}\s+{_FLOAT_RE}\s+{_FLOAT_RE}",
    re.IGNORECASE,
)
_NET_PAYER_RE = re.compile(
    r"Net [àa] payer au salari[eé].*?\n\s*([\d\s]+[.,]\d{2})",
    re.IGNORECASE | re.DOTALL,
)
_COUT_EMP_RE = re.compile(
    r"Vers[eé] employeur\s+([\d\s]+[.,]\d{2})",
    re.IGNORECASE,
)
_RUBRIC_LINE_RE = re.compile(
    r"^\s{4,}(.+?)\s+"
    r"(-?[\d\s]+[.,]\d{2,4}|-?\d+)\s*"
    r"(?:([\d\s]+[.,]\d{2,4}|\d+)\s+)?"
    r"(?:(-?[\d\s]+[.,]\d{2,4}|-?\d+)\s*)?"
    r"(?:(-?[\d\s]+[.,]\d{2,4}|-?\d+)\s*)?$"
)
_SKIP_PREFIXES = (
    "Q100",
    "Q200",
    "Q300",
    "Q400",
    "Q500",
    "Q600",
    "Q800",
    "Q801",
    "Q802",
    "EPR",
    "EMU",
    "EWA",
    "EWZ",
    "SINT",
    "SNDF",
    "Convention",
    "Pour plus",
    "Dans votre",
    "A défaut",
    "dont évolution",
    "Impôt sur le revenu",
    "Montant net",
    "MONTANT NET",
    "NET A PAYER",
    "NET IMPOSABLE",
    "SALAIRE BRUT",
    "TOTAL DES RETENUES",
    "Cotis.",
)


def _parse_float(raw: str | None) -> Optional[float]:
    if raw is None:
        return None
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    if not cleaned or cleaned in ("-", "—"):
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def _extract_last_float(pattern: re.Pattern[str], text: str) -> Optional[float]:
    matches = pattern.findall(text)
    if not matches:
        return None
    last = matches[-1]
    if isinstance(last, tuple):
        last = last[-1]
    return _parse_float(str(last))


def _split_by_matricule(full_text: str) -> Dict[str, str]:
    parts: Dict[str, List[str]] = {}
    current_matricule: str | None = None
    current_lines: List[str] = []

    for line in full_text.splitlines():
        m = _MATRICULE_RE.search(line)
        if m:
            if current_matricule:
                parts.setdefault(current_matricule, []).append("\n".join(current_lines))
            current_matricule = m.group(1).strip().upper()
            current_lines = [line]
        elif current_matricule:
            current_lines.append(line)

    if current_matricule:
        parts.setdefault(current_matricule, []).append("\n".join(current_lines))

    merged: Dict[str, str] = {}
    for matricule, chunks in parts.items():
        merged[matricule] = "\n".join(chunks)
    return merged


def _parse_rubriques(text: str) -> List[ReferenceRubricLine]:
    rubriques: List[ReferenceRubricLine] = []
    seen: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or any(stripped.startswith(p) for p in _SKIP_PREFIXES):
            continue
        if "Rubriques" in stripped or "Mt patronal" in stripped:
            continue
        if any(kw in stripped for kw in ("Solde :", "Acquis :", "Total pris :", "CP N")):
            continue
        decimal_nums = re.findall(r"-?\d+[.,]\d{2,4}", line)
        if not decimal_nums:
            continue
        first_pos = line.find(decimal_nums[0])
        if first_pos < 0:
            continue
        libelle = line[:first_pos].strip()
        libelle = re.sub(r"^[A-Z]{2,4}\s+", "", libelle).strip()
        if len(libelle) < 3 or libelle.lower().startswith("siret"):
            continue
        key = libelle.lower()
        if key in seen:
            continue
        seen.add(key)
        parsed = [_parse_float(n) for n in decimal_nums]
        parsed = [p for p in parsed if p is not None]
        if not parsed:
            continue
        base = parsed[0] if len(parsed) >= 1 else None
        taux = parsed[1] if len(parsed) >= 3 else None
        montant = parsed[-1] if len(parsed) >= 2 else parsed[0]
        if len(parsed) == 1:
            taux = None
            montant = parsed[0]
        rubriques.append(
            ReferenceRubricLine(
                libelle=libelle,
                base=base,
                taux_salarial=taux,
                montant_salarial=montant,
                montant_patronal=None,
            )
        )
    return rubriques


def parse_cegid_block(matricule: str, text: str) -> ReferenceBulletin:
    nom_match = _NOM_RE.search(text)
    nir_match = _NIR_RE.search(text)
    coeff_match = _COEFF_RE.search(text)
    cp_match = _CP_SOLDE_RE.search(text)
    paiement_match = _PAIEMENT_RE.search(text)

    pas_montant = None
    pas_taux = None
    pas_match = _PAS_RE.search(text)
    if pas_match:
        pas_taux = _parse_float(pas_match.group(2))
        pas_montant = _parse_float(pas_match.group(3))

    net_a_payer = _extract_last_float(_NET_PAYER_RE, text)
    if net_a_payer is None:
        # Fallback: last standalone amount near bottom after MNS section
        tail = text.split("MONTANT NET SOCIAL")[-1] if "MONTANT NET SOCIAL" in text else text
        amounts = re.findall(r"\b(\d[\d\s]*[.,]\d{2})\b", tail[-600:])
        if amounts:
            net_a_payer = _parse_float(amounts[-1])

    return ReferenceBulletin(
        matricule=matricule.upper(),
        nom_complet=nom_match.group(1).strip() if nom_match else "",
        nir=nir_match.group(1).strip() if nir_match else "",
        salaire_brut=_extract_last_float(_BRUT_RE, text),
        net_imposable=_extract_last_float(_NET_IMP_RE, text),
        montant_net_social=_extract_last_float(_MNS_RE, text),
        net_avant_impot=_extract_last_float(_NET_AVANT_RE, text),
        pas_montant=pas_montant,
        pas_taux=pas_taux,
        net_a_payer=net_a_payer,
        cout_total_employeur=_extract_last_float(_COUT_EMP_RE, text),
        date_paiement=paiement_match.group(1).strip() if paiement_match else None,
        cp_solde_n=_parse_float(cp_match.group(1)) if cp_match else None,
        coefficient=int(coeff_match.group(1)) if coeff_match else None,
        rubriques=_parse_rubriques(text),
        raw_text=text,
    )


def parse_cegid_text(full_text: str) -> Dict[str, ReferenceBulletin]:
    """Découpe le texte complet et retourne un bulletin par matricule."""
    blocks = _split_by_matricule(full_text)
    return {
        matricule: parse_cegid_block(matricule, block)
        for matricule, block in blocks.items()
    }
