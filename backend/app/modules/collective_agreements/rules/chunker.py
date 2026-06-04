"""Découpage du texte CC pour l'extraction IA."""

from __future__ import annotations

import re
from typing import Iterable

from app.modules.collective_agreements.rules.constants import (
    KEYWORDS,
    MAX_EXTRACTION_CHARS,
    MAX_SCOUT_CHARS,
)

_ARTICLE_PATTERN = re.compile(
    r"(?i)(?:^|\n)\s*(?:article|art\.?)\s*([0-9]+[\w\.\-]*)",
    re.MULTILINE,
)
_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Nettoie le HTML Légifrance pour faciliter l'extraction IA."""
    cleaned = _HTML_TAG.sub(" ", text)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&#160;", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def build_scout_window(full_text: str, max_chars: int = MAX_SCOUT_CHARS) -> str:
    """
    Construit une fenêtre de texte autour des mots-clés paie pour le repérage.
    Si le texte est court, le retourne entier.
    """
    if len(full_text) <= max_chars:
        return full_text

    lower = full_text.lower()
    positions: list[int] = []
    for kw in KEYWORDS:
        start = 0
        kw_lower = kw.lower()
        while True:
            pos = lower.find(kw_lower, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + len(kw_lower)

    if not positions:
        return full_text[:max_chars]

    positions.sort()
    half = max_chars // 2
    segments: list[str] = []
    used: set[tuple[int, int]] = set()

    for pos in positions:
        start = max(0, pos - half)
        end = min(len(full_text), pos + half)
        key = (start // 1000, end // 1000)
        if key in used:
            continue
        used.add(key)
        segments.append(full_text[start:end])
        if sum(len(s) for s in segments) >= max_chars:
            break

    combined = "\n\n[...]\n\n".join(segments)
    return combined[:max_chars]


def extract_article_blocks(
    full_text: str,
    article_refs: Iterable[str],
    max_chars: int = MAX_EXTRACTION_CHARS,
) -> str:
    """Extrait les blocs d'articles identifiés par le repérage."""
    refs = [r.strip() for r in article_refs if r and r.strip()]
    if not refs:
        return build_payroll_focused_text(full_text, max_chars)

    matches = list(_ARTICLE_PATTERN.finditer(full_text))
    if not matches:
        return build_fallback_sample(full_text, max_chars)

    blocks: list[str] = []
    total = 0

    for ref in refs:
        ref_norm = ref.lower().lstrip("art.").strip()
        for idx, match in enumerate(matches):
            art_num = match.group(1).lower()
            if art_num != ref_norm and not art_num.startswith(ref_norm):
                continue
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
            block = full_text[start:end].strip()
            if block and block not in blocks:
                blocks.append(block)
                total += len(block)
            break
        if total >= max_chars:
            break

    if not blocks:
        return build_payroll_focused_text(full_text, max_chars)

    combined = "\n\n---\n\n".join(blocks)
    return combined[:max_chars]


def build_fallback_sample(full_text: str, max_chars: int = MAX_EXTRACTION_CHARS) -> str:
    """Échantillon structuré si repérage vide : début + fenêtres mots-clés."""
    parts: list[str] = []
    head = full_text[: min(15_000, len(full_text))]
    parts.append(head)
    scout = build_scout_window(full_text, max_chars=max_chars - len(head))
    if scout not in parts:
        parts.append(scout)
    combined = "\n\n[...]\n\n".join(parts)
    return combined[:max_chars]


def build_payroll_focused_text(
    full_text: str, max_chars: int = MAX_EXTRACTION_CHARS
) -> str:
    """Fenêtre ciblée paie : textes salariaux, tableaux €, grilles, ancienneté."""
    parts: list[str] = []
    lower = full_text.lower()

    for marker in (
        "## texte salarial",
        "salaires minimaux",
        "textes salaires",
        "grille",
        "coefficient",
        "prime d'ancienneté",
        "prime d'anciennete",
        "article 7.1",
        "annexe",
    ):
        start = 0
        while True:
            pos = lower.find(marker, start)
            if pos == -1:
                break
            chunk = full_text[max(0, pos - 400) : min(len(full_text), pos + 6000)]
            if chunk not in parts:
                parts.append(chunk)
            start = pos + len(marker)
            if sum(len(p) for p in parts) >= max_chars:
                break
        if sum(len(p) for p in parts) >= max_chars:
            break

    if not parts:
        return build_fallback_sample(full_text, max_chars=max_chars)

    combined = "\n\n---\n\n".join(parts)
    return combined[:max_chars]
