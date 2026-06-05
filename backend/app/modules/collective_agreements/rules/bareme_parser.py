"""Parser déterministe du barème SMH national (métallurgie IDCC 3248)."""

from __future__ import annotations

import re
from typing import Optional

from app.modules.collective_agreements.rules.schema import GrilleSalaires, SalaireMinimum

# Groupe A-I, classe 1-18, montant en euros (annuel ou mensuel)
_SMH_ROW = re.compile(
    r"(?i)"
    r"(?:^|[\s|])"
    r"([A-I])\b"
    r"[\s|]+"
    r"(\d{1,2})"
    r"[\s|]+"
    r"([\d\s\u00a0]+(?:[,.]\d+)?)"
    r"\s*(?:€|euros?)"
)

_YEAR_IN_TEXT = re.compile(r"(20\d{2})")

# Seuil : montants annuels SMH métallurgie > 15 000 €, mensuels > 1 200 €
_ANNUAL_THRESHOLD = 15_000.0
_MONTHLY_THRESHOLD = 1_200.0


def _parse_euro_amount(raw: str) -> float:
    cleaned = raw.replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    return float(cleaned)


def _normalize_to_monthly(amount: float) -> float:
    """Convertit un montant annuel SMH en mensuel si nécessaire."""
    if amount >= _ANNUAL_THRESHOLD:
        return round(amount / 12, 2)
    return round(amount, 2)


def _extract_date_effet(text: str) -> Optional[str]:
    lower = text.lower()
    for marker in (
        "barème unique des salaires minima hiérarchiques",
        "bareme unique des salaires minima hierarchiques",
        "salaires minima hiérarchiques",
        "minima hiérarchiques",
    ):
        pos = lower.find(marker)
        if pos >= 0:
            window = text[pos : pos + 500]
            years = _YEAR_IN_TEXT.findall(window)
            if years:
                return years[-1]
    years = _YEAR_IN_TEXT.findall(text[:5000])
    return years[-1] if years else None


def parse_smh_national(text: str) -> Optional[GrilleSalaires]:
    """
    Extrait le barème national SMH (groupes A-I, classes 1-18) depuis un texte KALI.

    Retourne None si moins de 10 lignes plausibles (évite faux positifs).
    """
    if not text or len(text.strip()) < 200:
        return None

    by_classe: dict[int, SalaireMinimum] = {}
    groupe_par_classe: dict[int, str] = {}

    for match in _SMH_ROW.finditer(text):
        groupe = match.group(1).upper()
        classe = int(match.group(2))
        if classe < 1 or classe > 18:
            continue
        try:
            amount = _parse_euro_amount(match.group(3))
        except ValueError:
            continue
        if amount < _MONTHLY_THRESHOLD and amount < _ANNUAL_THRESHOLD:
            continue
        monthly = _normalize_to_monthly(amount)
        if monthly < _MONTHLY_THRESHOLD:
            continue
        by_classe[classe] = SalaireMinimum(
            coefficient=float(classe),
            valeur=monthly,
            libelle=f"Groupe {groupe} — Classe {classe}",
        )
        groupe_par_classe[classe] = groupe

    if len(by_classe) < 10:
        return None

    minima = [by_classe[c] for c in sorted(by_classe)]
    date_effet = _extract_date_effet(text)

    return GrilleSalaires(
        zone_type="national",
        zone_libelle="National — SMH",
        minima=minima,
        date_effet=date_effet,
        source_titre="Barème unique des salaires minima hiérarchiques",
    )
