"""Filtre des alertes bruit import pointages (hybride IA + LLM)."""

from __future__ import annotations

import re

_NOISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"single_channel_extraction", re.I),
    re.compile(r"extraction vision seule", re.I),
    re.compile(r"extraction texte seule", re.I),
    re.compile(r"écart vision/ocr", re.I),
    re.compile(
        r"employee\s*['\"].+['\"]\s*not found|employee.*not found|"
        r"not found in (the )?(provided )?text|employé.*introuvable",
        re.I,
    ),
    re.compile(r"^for .+, the note\b", re.I),
    re.compile(r"\bindicates a (leave|sick leave)\b", re.I),
    re.compile(r"\bis unclear\b", re.I),
    re.compile(r"\bsuggests a\b", re.I),
    re.compile(r"\bpotential issue\b", re.I),
    re.compile(r"\bmissing hours\b", re.I),
    re.compile(r"\bare unclear in their meaning\b", re.I),
    re.compile(r"le total hebdomadaire pour .+ n'est pas visible", re.I),
    re.compile(r"le total hebdomadaire pour .+ est \d", re.I),
    re.compile(r"légère différence", re.I),
    re.compile(r"le calcul des heures individuelles donne", re.I),
    re.compile(r"^[^:]+:\s*single_channel_extraction", re.I),
    re.compile(r"PDF de \d+ pages?, seules \d+ pages?", re.I),
    re.compile(r"seules \d+ pages? (traitées|OCRisées)", re.I),
    re.compile(r"cheval sur deux mois", re.I),
)


def is_timesheet_noise_warning(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return True
    return any(p.search(text) for p in _NOISE_PATTERNS)


def filter_timesheet_warnings(warnings: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for w in warnings:
        text = (w or "").strip()
        if not text or is_timesheet_noise_warning(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


__all__ = ["filter_timesheet_warnings", "is_timesheet_noise_warning"]
