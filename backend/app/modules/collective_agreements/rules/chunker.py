"""Découpage du texte CC pour l'extraction IA."""

from __future__ import annotations

import re
from typing import Iterable

from app.modules.collective_agreements.rules.constants import (
    KEYWORDS,
    MAX_EXTRACTION_CHARS,
    MAX_GRILLE_CHUNK_CHARS,
    MAX_GRILLE_EXTRACTION_CHUNKS,
    MAX_SCOUT_CHARS,
)

_ARTICLE_PATTERN = re.compile(
    r"(?i)(?:^|\n)\s*(?:article|art\.?)\s*([0-9]+[\w\.\-]*)",
    re.MULTILINE,
)
_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Nettoie le HTML Légifrance en conservant la structure (titres ##)."""
    cleaned = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"</(?:p|div|tr|td|th|li|h[1-6]|table|section|article)>\s*",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = _HTML_TAG.sub(" ", cleaned)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&#160;", " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
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
        "classification",
        "coefficient",
        "positionnement",
        "valeur du point",
        "valeur de point",
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


def build_minima_focused_text(
    full_text: str, max_chars: int = MAX_EXTRACTION_CHARS
) -> str:
    """Fenêtre ciblée grilles / classification (sans prime d'ancienneté)."""
    parts: list[str] = []
    lower = full_text.lower()

    for marker in (
        "## texte salarial",
        "salaires minimaux",
        "textes salaires",
        "grille de classification",
        "grille des salaires",
        "grille",
        "classification",
        "coefficient",
        "positionnement",
        "valeur du point",
        "valeur de point",
        "annexe",
        "tableau des",
    ):
        start = 0
        while True:
            pos = lower.find(marker, start)
            if pos == -1:
                break
            chunk = full_text[max(0, pos - 400) : min(len(full_text), pos + 8000)]
            if chunk not in parts:
                parts.append(chunk)
            start = pos + len(marker)
            if sum(len(p) for p in parts) >= max_chars:
                break
        if sum(len(p) for p in parts) >= max_chars:
            break

    if not parts:
        return build_payroll_focused_text(full_text, max_chars=max_chars)

    combined = "\n\n---\n\n".join(parts)
    return combined[:max_chars]


_SALARY_BLOCK_PATTERN = re.compile(
    r"(?=##\s*(?:Texte salarial|Rémunération|Remuneration|Annexe|Classification|Grille|Positionnement))",
    re.IGNORECASE,
)

_GEO_ZONE_PATTERN = re.compile(
    r"(?=(?:Pour la |Pour le département |Pour les départements |"
    r"Dans le département |En région |Région ))",
    re.IGNORECASE,
)


def split_salary_grille_chunks(
    full_text: str,
    *,
    max_chunk_chars: int = MAX_GRILLE_CHUNK_CHARS,
) -> list[str]:
    """
    Découpe le texte KALI en blocs salariaux pour extraction multi-grilles.
    Retourne une liste vide si un seul bloc global suffit.
    """
    if not full_text or len(full_text.strip()) < 80:
        return []

    parts = _SALARY_BLOCK_PATTERN.split(full_text)
    chunks: list[str] = []
    for part in parts:
        block = part.strip()
        if not block:
            continue
        if not _looks_like_salary_block(block):
            continue
        for geo_block in _subsplit_geo_zones(block):
            trimmed = geo_block.strip()
            if not trimmed or not _looks_like_salary_block(trimmed):
                continue
            if len(trimmed) > max_chunk_chars:
                trimmed = trimmed[:max_chunk_chars]
            chunks.append(trimmed)

    return _dedupe_and_cap_salary_chunks(chunks)


def _dedupe_and_cap_salary_chunks(chunks: list[str]) -> list[str]:
    """Déduplique par zone et limite le nombre d'appels IA."""
    by_key: dict[str, str] = {}
    for chunk in chunks:
        key = _chunk_zone_key(chunk)
        prev = by_key.get(key)
        if not prev or _chunk_recency_score(chunk) >= _chunk_recency_score(prev):
            by_key[key] = chunk
    deduped = sorted(
        by_key.values(),
        key=_chunk_recency_score,
        reverse=True,
    )
    if len(deduped) > MAX_GRILLE_EXTRACTION_CHUNKS:
        deduped = deduped[:MAX_GRILLE_EXTRACTION_CHUNKS]
    if len(deduped) >= 2:
        return deduped
    # Bloc national unique volumineux (ex. métallurgie 3248) : extraction dédiée
    if len(deduped) == 1 and len(deduped[0]) >= 1500:
        return deduped
    return []


def _chunk_zone_key(chunk: str) -> str:
    title_match = re.search(r"##\s*Texte salarial\s*:\s*(.+)", chunk, re.IGNORECASE)
    if title_match:
        return _salary_zone_key_from_chunk_title(title_match.group(1))
    geo_match = re.search(
        r"(?:Pour la |Pour le département )(.{3,50}?)[,\.\n:]",
        chunk,
        re.IGNORECASE,
    )
    if geo_match:
        return geo_match.group(1).strip().lower()
    return chunk[:120].lower()


def _salary_zone_key_from_chunk_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(title).strip())
    if " - " in cleaned:
        return cleaned.rsplit(" - ", 1)[-1].strip().lower()
    return cleaned.lower()[:80]


def _chunk_recency_score(chunk: str) -> int:
    years = [int(y) for y in re.findall(r"(20\d{2})", chunk[:500])]
    return max(years) if years else 0


def _subsplit_geo_zones(block: str) -> list[str]:
    """Sous-découpe un texte salarial contenant plusieurs zones géographiques."""
    stripped = block.strip()
    if re.match(r"(?:##\s*)?Texte salarial", stripped, re.IGNORECASE):
        return [block]
    matches = list(_GEO_ZONE_PATTERN.finditer(block))
    if len(matches) <= 1:
        return [block]
    chunks: list[str] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        chunk = block[start:end].strip()
        if chunk and _looks_like_salary_block(chunk):
            chunks.append(chunk)
    return chunks if len(chunks) >= 2 else [block]


def _looks_like_salary_block(text: str) -> bool:
    lower = text.lower()
    has_money = "€" in text or "euro" in lower
    has_point = "valeur du point" in lower or "valeur de point" in lower
    has_grid = any(
        k in lower
        for k in (
            "coefficient",
            "salaire",
            "minima",
            "minimum",
            "grille",
            "position",
            "positionnement",
            "niveau",
            "classification",
            "point",
        )
    )
    return (has_money or has_point) and has_grid
