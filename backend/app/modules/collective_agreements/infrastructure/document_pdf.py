"""Génération des PDF de convention collective (texte intégral + synthèse IA).

Rendu HTML → PDF via WeasyPrint. Deux entrées :
- ``build_full_text_pdf`` : le texte KALI structuré (titres ##, articles) en PDF lisible.
- ``build_synthesis_pdf`` : une synthèse markdown (générée par IA) en PDF pédagogique.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import escape
from weasyprint import HTML

_BASE_CSS = """
@page {
    size: A4;
    margin: 2.2cm 1.8cm 2.4cm 1.8cm;
    @bottom-center {
        content: "Page " counter(page) " / " counter(pages);
        font-size: 8pt;
        color: #94a3b8;
    }
}
* { box-sizing: border-box; }
body {
    font-family: "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.5;
    color: #1e293b;
}
.doc-header {
    border-bottom: 2px solid #1e3a8a;
    padding-bottom: 12px;
    margin-bottom: 22px;
}
.doc-kicker {
    font-size: 8.5pt;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #1e3a8a;
    font-weight: 700;
}
.doc-title {
    font-size: 16pt;
    font-weight: 700;
    color: #0f172a;
    margin: 6px 0 4px 0;
}
.doc-meta {
    font-size: 9pt;
    color: #64748b;
}
h1 { font-size: 14pt; color: #1e3a8a; margin: 22px 0 8px 0; }
h2 {
    font-size: 12.5pt;
    color: #1e3a8a;
    margin: 20px 0 6px 0;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 3px;
}
h3 { font-size: 11pt; color: #334155; margin: 14px 0 4px 0; }
p { margin: 6px 0; text-align: justify; }
ul { margin: 6px 0 6px 0; padding-left: 18px; }
li { margin: 3px 0; }
strong { color: #0f172a; }
.article-label {
    font-weight: 700;
    color: #1e3a8a;
    margin-top: 12px;
}
.table-wrap { margin: 10px auto; max-width: 100%; }
table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 9.5pt; }
th, td { border: 1px solid #cbd5e1; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #f1f5f9; }
.footnote {
    font-size: 8.5pt;
    color: #64748b;
    font-style: italic;
    margin: 8px 0;
    padding-left: 10px;
    border-left: 2px solid #cbd5e1;
}
.disclaimer {
    margin-top: 26px;
    padding: 10px 12px;
    background: #f8fafc;
    border-left: 3px solid #94a3b8;
    font-size: 8.5pt;
    color: #64748b;
}
"""


def _now_fr() -> str:
    return datetime.now(timezone.utc).strftime("%d/%m/%Y")


def _wrap_html(*, kicker: str, title: str, idcc: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><style>{_BASE_CSS}</style></head>
<body>
<div class="doc-header">
    <div class="doc-kicker">{escape(kicker)}</div>
    <div class="doc-title">{escape(title)}</div>
    <div class="doc-meta">IDCC {escape(idcc)} &middot; Document généré le {_now_fr()}</div>
</div>
{body_html}
<div class="disclaimer">
    Document généré automatiquement à partir du texte publié sur Légifrance (fonds KALI).
    Il est fourni à titre informatif et ne se substitue pas au texte officiel ni à un conseil juridique.
    Vérifiez toujours la version en vigueur sur legifrance.gouv.fr.
</div>
</body></html>"""


def _render_pdf(html_str: str) -> bytes:
    return HTML(string=html_str).write_pdf()


# --- Rendu texte KALI structuré -------------------------------------------------

_ARTICLE_LINE = re.compile(r"^article\s+([\w.\-]+)\s*$", re.IGNORECASE)
_KALI_ARTICLE_ID = re.compile(r"^article\s+KALIARTI\d+\s*$", re.IGNORECASE)
_SOURCE_LINE = re.compile(r"^source\s*:", re.IGNORECASE)
_IDCC_LINE = re.compile(r"^idcc\s+\d+\s*$", re.IGNORECASE)
_HTML_HINT = re.compile(r"<\s*/?\s*(?:p|table|tr|td|th|div|center|br|font|a|em|strong|i|b)\b", re.IGNORECASE)
_BLOCK_SPLIT = re.compile(r"\n{2,}")


def _normalize_idcc_variants(idcc: str) -> set[str]:
    stripped = idcc.strip()
    variants = {stripped, stripped.lstrip("0") or "0"}
    if stripped.isdigit():
        variants.add(stripped.zfill(4))
    return variants


def _normalize_block_breaks(text: str) -> str:
    """Insère des séparations de blocs là où KALI utilise une seule newline."""
    cleaned = re.sub(r"\n---+\n", "\n\n", text)
    cleaned = re.sub(
        r"\n(Article\s+[\w.\-]+\s*\n)",
        r"\n\n\1",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?m)^([^\n#<][^\n]{4,120})\n(Article\s+)",
        r"\1\n\n\2",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _maybe_section_title(text: str) -> str | None:
    """Titres de section KALI sans marqueur markdown (ex. avant un article)."""
    single = text.strip()
    if not single or "\n" in single or len(single) > 120:
        return None
    if single.endswith((".", ":", ";")) or _HTML_HINT.search(single):
        return None
    if _ARTICLE_LINE.match(single) or single.startswith("#"):
        return None
    words = single.split()
    if len(words) < 2:
        return None
    return f"<h3>{escape(single)}</h3>"


def _prepare_kali_text(full_text: str, *, idcc: str) -> str:
    """Retire le préambule catalogue et les lignes métadonnées redondantes."""
    text = full_text.replace("\r\n", "\n")
    idcc_variants = _normalize_idcc_variants(idcc)
    lines: list[str] = []
    skip_preamble = True

    for raw in text.split("\n"):
        stripped = raw.strip()
        if skip_preamble:
            if not stripped:
                continue
            if stripped.startswith("# "):
                continue
            if _IDCC_LINE.match(stripped):
                upper = stripped.upper().replace("IDCC ", "")
                if upper in idcc_variants or upper.zfill(4) in idcc_variants:
                    continue
            if _SOURCE_LINE.match(stripped):
                continue
            skip_preamble = False

        if _SOURCE_LINE.match(stripped):
            continue
        if _IDCC_LINE.match(stripped):
            upper = stripped.upper().replace("IDCC ", "")
            if upper in idcc_variants or upper.zfill(4) in idcc_variants:
                continue
        if _KALI_ARTICLE_ID.match(stripped):
            continue
        if stripped in ("###", "---", "___", "***"):
            continue
        lines.append(raw)

    return "\n".join(lines).strip()


def _sanitize_legifrance_html(html: str) -> str:
    """Nettoie le HTML Légifrance pour WeasyPrint (tableaux, notes d'extension)."""
    cleaned = html.replace("\r\n", "\n")
    cleaned = re.sub(
        r"<a\b[^>]*>(.*?)</a>",
        r"\1",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(r"<a\b[^>]*/?>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r'<font\s+color=["\']?#?808080["\']?\s*>',
        '<aside class="footnote">',
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"</font>", "</aside>", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<font[^>]*>\s*</font>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<center\b[^>]*>", '<div class="table-wrap">', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</center>", "</div>", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+align=\"[^\"]*\"", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+align=\'[^\']*\'', "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+border="[^"]*"', "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"<p[^>]*>\s*(?:<br\s*/?>\s*)*\s*</p>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.replace("&nbsp;", " ").replace("&#160;", " ")
    return cleaned.strip()


def _normalize_plain(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed.casefold()


def _title_from_h2(heading: str) -> str:
    title = heading.strip()
    prefix = "texte salarial : "
    if title.casefold().startswith(prefix):
        return title[len(prefix) :].strip()
    return title


def _is_duplicate_section_title(section_title: str, plain_block: str) -> bool:
    block_norm = _normalize_plain(plain_block)
    if not block_norm:
        return True
    for candidate in (_title_from_h2(section_title), section_title.strip()):
        if block_norm == _normalize_plain(candidate):
            return True
    return False


def _render_plain_block(text: str) -> str:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return ""
    joined = " ".join(lines)
    return f"<p>{escape(joined)}</p>"


def _render_kali_text_to_html(full_text: str, *, idcc: str = "") -> str:
    prepared = _normalize_block_breaks(_prepare_kali_text(full_text, idcc=idcc))
    if not prepared:
        return ""

    out: list[str] = []
    last_h2: str | None = None

    for block in _BLOCK_SPLIT.split(prepared):
        stripped = block.strip()
        if not stripped:
            continue

        if stripped.startswith("#### "):
            out.append(f"<h3>{escape(stripped[5:].strip())}</h3>")
            last_h2 = None
            continue
        if stripped.startswith("### "):
            out.append(f"<h3>{escape(stripped[4:].strip())}</h3>")
            last_h2 = None
            continue
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            out.append(f"<h2>{escape(heading)}</h2>")
            last_h2 = heading
            continue
        if stripped.startswith("# "):
            out.append(f"<h1>{escape(stripped[2:].strip())}</h1>")
            last_h2 = None
            continue

        if _ARTICLE_LINE.match(stripped) and "\n" not in stripped and len(stripped) < 80:
            if _KALI_ARTICLE_ID.match(stripped):
                continue
            out.append(f'<p class="article-label">{escape(stripped)}</p>')
            continue

        first_line, _, rest = stripped.partition("\n")
        if _ARTICLE_LINE.match(first_line) and len(first_line) < 80 and not _KALI_ARTICLE_ID.match(first_line):
            out.append(f'<p class="article-label">{escape(first_line)}</p>')
            body = rest.strip()
            if not body:
                continue
            if _HTML_HINT.search(body):
                out.append(_sanitize_legifrance_html(body))
            elif last_h2 and _is_duplicate_section_title(last_h2, body):
                continue
            else:
                out.append(_render_plain_block(body))
            continue

        if _HTML_HINT.search(stripped):
            out.append(_sanitize_legifrance_html(stripped))
            continue

        if last_h2 and _is_duplicate_section_title(last_h2, stripped):
            continue

        section_title = _maybe_section_title(stripped)
        if section_title:
            out.append(section_title)
            continue

        rendered = _render_plain_block(stripped)
        if rendered:
            out.append(rendered)

    return "\n".join(out)


def build_full_text_pdf(*, title: str, idcc: str, full_text: str) -> bytes:
    body = _render_kali_text_to_html(full_text, idcc=idcc)
    if not body.strip():
        body = "<p>Aucun contenu textuel disponible pour cette convention.</p>"
    html_str = _wrap_html(
        kicker="Convention collective — Texte intégral",
        title=title,
        idcc=idcc,
        body_html=body,
    )
    return _render_pdf(html_str)


# --- Rendu markdown synthèse IA -------------------------------------------------

_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline_md(text: str) -> str:
    escaped = escape(text)
    return _BOLD.sub(r"<strong>\1</strong>", escaped)


def _render_markdown_to_html(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    bullets: list[str] = []

    def flush_para() -> None:
        if para:
            joined = " ".join(s.strip() for s in para if s.strip())
            if joined:
                out.append(f"<p>{_inline_md(joined)}</p>")
            para.clear()

    def flush_bullets() -> None:
        if bullets:
            items = "".join(f"<li>{_inline_md(b)}</li>" for b in bullets)
            out.append(f"<ul>{items}</ul>")
            bullets.clear()

    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            flush_para()
            flush_bullets()
            continue
        if stripped.startswith("### "):
            flush_para()
            flush_bullets()
            out.append(f"<h3>{_inline_md(stripped[4:].strip())}</h3>")
        elif stripped.startswith("## "):
            flush_para()
            flush_bullets()
            out.append(f"<h2>{_inline_md(stripped[3:].strip())}</h2>")
        elif stripped.startswith("# "):
            flush_para()
            flush_bullets()
            out.append(f"<h1>{_inline_md(stripped[2:].strip())}</h1>")
        elif stripped[:2] in ("- ", "* ") or stripped.startswith("• "):
            flush_para()
            bullets.append(stripped[2:].strip())
        else:
            flush_bullets()
            para.append(stripped)
    flush_para()
    flush_bullets()
    return "\n".join(out)


def build_synthesis_pdf(*, title: str, idcc: str, synthesis_md: str) -> bytes:
    body = _render_markdown_to_html(synthesis_md)
    if not body.strip():
        body = "<p>Synthèse indisponible.</p>"
    html_str = _wrap_html(
        kicker="Convention collective — Synthèse expliquée",
        title=title,
        idcc=idcc,
        body_html=body,
    )
    return _render_pdf(html_str)
