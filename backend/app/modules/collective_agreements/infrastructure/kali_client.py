"""Client API PISTE / Légifrance (fond KALI — conventions collectives)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 400_000
MAX_ARTICLE_FETCHES = 250
MIN_FETCHED_TEXT_CHARS = 200


@dataclass
class KaliConventionMeta:
    idcc: str
    kalicont_id: str
    title: str
    legifrance_url: str


@dataclass
class KaliFetchResult:
    meta: KaliConventionMeta
    full_text: str
    character_count: int
    sections_fetched: int
    articles_fetched: int


class PisteNotConfiguredError(Exception):
    """PISTE_CLIENT_ID / PISTE_CLIENT_SECRET absents."""


class KaliNotFoundError(Exception):
    """Aucune convention KALI pour cet IDCC."""


class KaliClient:
    """Accès OAuth + endpoints consult/list KALI."""

    def __init__(
        self,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        sandbox: Optional[bool] = None,
    ):
        self._client_id = (client_id or os.environ.get("PISTE_CLIENT_ID") or "").strip()
        self._client_secret = (
            client_secret or os.environ.get("PISTE_CLIENT_SECRET") or ""
        ).strip()
        use_sandbox = sandbox if sandbox is not None else _env_flag("PISTE_SANDBOX")
        if use_sandbox:
            self._url_token = "https://sandbox-oauth.piste.gouv.fr/api/oauth/token"
            self._url_api = (
                "https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app"
            )
        else:
            self._url_token = "https://oauth.piste.gouv.fr/api/oauth/token"
            self._url_api = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
        self._token: Optional[str] = None
        self._token_expires_at = 0.0

    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def require_configured(self) -> None:
        if not self.is_configured():
            raise PisteNotConfiguredError(
                "PISTE_CLIENT_ID et PISTE_CLIENT_SECRET requis. "
                "Inscrivez-vous sur https://piste.gouv.fr"
            )

    def fetch_convention_text(self, idcc: str) -> KaliFetchResult:
        """Récupère le texte officiel KALI pour un IDCC (priorité paie)."""
        self.require_configured()
        meta = self.resolve_convention(idcc)
        cont = self._post("consult/kaliCont", {"id": meta.kalicont_id})
        if not cont:
            raise KaliNotFoundError(f"Conteneur KALI introuvable pour IDCC {idcc}")

        cont_data = cont.get("conteneur") or cont
        top_sections = cont_data.get("sections") or []
        if not top_sections:
            raise KaliNotFoundError(f"Aucune section pour IDCC {idcc}")

        parts: list[str] = [
            f"# {meta.title}",
            f"IDCC {meta.idcc}",
            f"Source : {meta.legifrance_url}",
            "",
        ]
        articles_fetched = 0
        sections_fetched = 0

        # 1. Textes Salaires récents (grilles € + coefficients)
        salary_blocks, af, sf = self._collect_salary_texts(top_sections)
        parts.extend(salary_blocks)
        articles_fetched += af
        sections_fetched += sf

        # 2. Annexes classification (Textes Attachés)
        annex_blocks, af, sf = self._collect_payroll_annexes(top_sections)
        parts.extend(annex_blocks)
        articles_fetched += af
        sections_fetched += sf

        # 3. Extraits rémunération / prime depuis le texte de base
        rem_blocks, af, sf = self._collect_remuneration_excerpts(top_sections)
        parts.extend(rem_blocks)
        articles_fetched += af
        sections_fetched += sf

        if len(parts) <= 4:
            # Fallback : texte de base en vigueur (comportement legacy)
            base = _pick_base_section(top_sections)
            if base:
                sections_fetched += 1
                lines: list[str] = []
                articles_fetched += self._append_section_content(base, lines)
                parts.extend(lines)

        full_text = _truncate("\n\n".join(p for p in parts if p))
        if len(full_text.strip()) < MIN_FETCHED_TEXT_CHARS:
            raise KaliNotFoundError(
                f"Texte KALI insuffisant pour IDCC {idcc} (contenu paie introuvable)"
            )

        return KaliFetchResult(
            meta=meta,
            full_text=full_text,
            character_count=len(full_text),
            sections_fetched=sections_fetched,
            articles_fetched=articles_fetched,
        )

    def _collect_salary_texts(
        self, top_sections: list[Any]
    ) -> tuple[list[str], int, int]:
        blocks: list[str] = []
        articles = 0
        sections = 0
        for top in top_sections:
            if not _section_title_matches(top, "textes salaires"):
                continue
            subs = _filter_vigueur_sections(top.get("sections") or [])
            candidates = [s for s in subs if _is_salary_kalitext(s)]
            for sub in candidates[-3:]:
                sections += 1
                text, af = self._fetch_subsection_text(sub)
                if text:
                    blocks.append(f"## Texte salarial : {sub.get('title', '').strip()}\n\n{text}")
                    articles += af
                time.sleep(0.12)
        return blocks, articles, sections

    def _collect_payroll_annexes(
        self, top_sections: list[Any]
    ) -> tuple[list[str], int, int]:
        blocks: list[str] = []
        articles = 0
        sections = 0
        seen: set[str] = set()
        for top in top_sections:
            if not _section_title_matches(top, "textes attach"):
                continue
            subs = _filter_vigueur_sections(top.get("sections") or [])
            for sub in reversed(subs):
                title = str(sub.get("title") or "")
                if not _is_payroll_annex(title):
                    continue
                key = _annex_dedupe_key(title)
                if key in seen:
                    continue
                seen.add(key)
                sections += 1
                text, af = self._fetch_subsection_text(sub)
                if text:
                    blocks.append(f"## {title.strip()}\n\n{text}")
                    articles += af
                time.sleep(0.12)
                if len(seen) >= 6:
                    break
        return blocks, articles, sections

    def _collect_remuneration_excerpts(
        self, top_sections: list[Any]
    ) -> tuple[list[str], int, int]:
        base = _pick_base_section(top_sections)
        if not base:
            return [], 0, 0
        text, articles = self._fetch_subsection_text(base)
        if not text:
            return [], 0, 0
        excerpt = _extract_remuneration_excerpt(text)
        if not excerpt:
            return [], articles, 1
        return [f"## Rémunération (texte de base)\n\n{excerpt}"], articles, 1

    def _fetch_subsection_text(self, sub: dict[str, Any]) -> tuple[str, int]:
        text_id = str(sub.get("id") or "")
        lines: list[str] = []
        if text_id.startswith("KALITEXT"):
            kali_text = self._post("consult/kaliText", {"id": text_id})
            if not kali_text:
                return "", 0
            articles = self._append_section_content(kali_text, lines)
        else:
            articles = self._append_section_content(sub, lines)
        return "\n".join(lines).strip(), articles

    def _append_section_content(
        self, section: dict[str, Any], lines: list[str], *, depth: int = 0
    ) -> int:
        return self._append_section_text(section, lines, depth=depth)

    def resolve_convention(self, idcc: str) -> KaliConventionMeta:
        """Trouve le KALICONT et le titre pour un IDCC."""
        for candidate in _idcc_variants(idcc):
            meta = self._resolve_from_list(candidate)
            if meta:
                return meta
            meta = self._resolve_from_search(candidate)
            if meta:
                return meta
        raise KaliNotFoundError(f"Aucune convention KALI trouvée pour IDCC {idcc}")

    def _resolve_from_list(self, idcc: str) -> Optional[KaliConventionMeta]:
        data = self._post(
            "list/conventions",
            {
                "pageSize": 5,
                "pageNumber": 1,
                "idcc": idcc.lstrip("0") or idcc,
                "legalStatus": ["VIGUEUR", "VIGUEUR_DIFF"],
                "sort": "DATE_PUBLI_DESC",
            },
        )
        if not data:
            return None
        for row in data.get("results") or []:
            kalicont_id = _extract_kalicont_id(row)
            if not kalicont_id:
                continue
            title = (
                row.get("titre")
                or row.get("title")
                or row.get("titles", [{}])[0].get("title")
            )
            if not title or str(title).lower().startswith("arrêté"):
                cont = self._post("consult/kaliCont", {"id": kalicont_id})
                if cont:
                    cont_data = cont.get("conteneur") or cont
                    title = cont_data.get("title") or cont_data.get("titre") or title
            title = str(title or f"Convention IDCC {idcc}").strip()
            return KaliConventionMeta(
                idcc=_normalize_idcc(idcc),
                kalicont_id=kalicont_id,
                title=title,
                legifrance_url=_legifrance_url(kalicont_id),
            )
        return None

    def _resolve_from_search(self, idcc: str) -> Optional[KaliConventionMeta]:
        data = self._post(
            "search",
            {
                "recherche": {
                    "fond": "KALI",
                    "champs": [
                        {
                            "typeChamp": "IDCC",
                            "criteres": [{"typeRecherche": "EXACTE", "valeur": idcc}],
                        }
                    ],
                    "pageNumber": 1,
                    "pageSize": 5,
                    "sort": "CHRONO_DATE_PUBLI",
                }
            },
        )
        if not data:
            return None
        for row in data.get("results") or []:
            kalicont_id = _extract_kalicont_id(row)
            if not kalicont_id:
                continue
            titles = row.get("titles") or []
            title = titles[0].get("title") if titles else f"Convention IDCC {idcc}"
            return KaliConventionMeta(
                idcc=_normalize_idcc(idcc),
                kalicont_id=kalicont_id,
                title=str(title).strip(),
                legifrance_url=_legifrance_url(kalicont_id),
            )
        return None

    def _append_section_text(
        self, section: dict[str, Any], lines: list[str], *, depth: int
    ) -> int:
        articles_fetched = 0
        prefix = "#" * min(2 + depth, 4)
        title = section.get("title") or section.get("titre")
        if title:
            lines.append(f"\n{prefix} {title}\n")

        for article in section.get("articles") or []:
            if articles_fetched >= MAX_ARTICLE_FETCHES:
                break
            text = article.get("texte") or article.get("content")
            art_id = article.get("id") or ""
            if not text and art_id:
                fetched = self._post("consult/getArticle", {"id": art_id})
                if fetched and isinstance(fetched.get("article"), dict):
                    text = fetched["article"].get("texte")
                    articles_fetched += 1
                    time.sleep(0.05)
            if text:
                label = article.get("num") or art_id
                lines.append(f"\nArticle {label}\n{text}\n")

        for sub in _filter_vigueur_sections(section.get("sections") or []):
            if _text_len(lines) >= MAX_TEXT_CHARS:
                break
            articles_fetched += self._append_section_text(sub, lines, depth=depth + 1)
        return articles_fetched

    def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "openid",
        }
        resp = requests.post(self._url_token, headers=headers, data=data, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires_at = now + int(payload.get("expires_in", 3600))
        return self._token

    def _post(self, path: str, body: dict[str, Any]) -> Optional[dict[str, Any]]:
        return self._post_with_retry(path, body)

    def _post_with_retry(
        self,
        path: str,
        body: dict[str, Any],
        *,
        _auth_retried: bool = False,
        _attempt: int = 0,
    ) -> Optional[dict[str, Any]]:
        token = self._get_token()
        url = f"{self._url_api}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            if resp.status_code == 401 and not _auth_retried:
                self._token = None
                self._token_expires_at = 0.0
                return self._post_with_retry(
                    path, body, _auth_retried=True, _attempt=_attempt
                )
            if resp.status_code in (502, 503, 504) and _attempt < 3:
                time.sleep(0.4 * (_attempt + 1))
                return self._post_with_retry(
                    path, body, _auth_retried=_auth_retried, _attempt=_attempt + 1
                )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            detail = ""
            if exc.response is not None:
                detail = exc.response.text[:500]
            logger.warning("KALI API %s échouée: %s %s", path, exc, detail)
            return None


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _idcc_variants(idcc: str) -> list[str]:
    stripped = idcc.strip()
    variants = [stripped, stripped.lstrip("0") or "0"]
    if stripped.isdigit():
        variants.append(stripped.zfill(4))
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _normalize_idcc(idcc: str) -> str:
    s = idcc.strip()
    if s.isdigit():
        return s.zfill(4) if len(s) <= 4 else s
    return s


def _extract_kalicont_id(row: dict[str, Any]) -> Optional[str]:
    cid_conteneur = row.get("cidConteneur")
    if isinstance(cid_conteneur, str) and cid_conteneur.startswith("KALICONT"):
        return cid_conteneur
    for key in ("id", "cid", "textId", "texteBaseId"):
        val = row.get(key)
        if isinstance(val, str) and val.startswith("KALICONT"):
            return val
    for key in ("id", "cid"):
        val = row.get(key)
        if isinstance(val, str) and "KALICONT" in val:
            m = re.search(r"KALICONT\d+", val)
            if m:
                return m.group(0)
    return None


def _legifrance_url(kalicont_id: str) -> str:
    return f"https://www.legifrance.gouv.fr/conv_coll/id/{kalicont_id}/"


def _filter_vigueur_sections(sections: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        etat = str(sec.get("etat") or "").upper()
        if etat.startswith("VIGUEUR") or not etat:
            out.append(sec)
    return out


def _pick_base_section(top_sections: list[Any]) -> Optional[dict[str, Any]]:
    candidates = [
        s
        for s in top_sections
        if isinstance(s, dict)
        and "texte de base" in str(s.get("title") or "").lower()
        and str(s.get("etat") or "").upper().startswith("VIGUEUR")
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda s: (
            0 if "ETEN" in str(s.get("etat") or "").upper() else 1,
            str(s.get("title") or ""),
        )
    )
    return candidates[0]


def _section_title_matches(section: dict[str, Any], needle: str) -> bool:
    return needle in str(section.get("title") or "").lower()


def _is_salary_kalitext(sub: dict[str, Any]) -> bool:
    title = str(sub.get("title") or "").lower()
    return (
        "salaire" in title
        or "rémunération" in title
        or "remuneration" in title
    )


def _is_payroll_annex(title: str) -> bool:
    t = title.lower()
    if "annexe" not in t:
        return False
    return any(
        k in t
        for k in (
            "classification",
            "grille",
            "salaire",
            "rémunération",
            "remuneration",
            "ingénieur",
            "ingenieur",
            "cadre",
            "etam",
        )
    )


def _annex_dedupe_key(title: str) -> str:
    t = title.lower()
    if "annexe i" in t or "annexe 1" in t:
        return "annexe1"
    if "annexe ii" in t or "annexe 2" in t:
        return "annexe2"
    if "annexe iii" in t or "annexe 3" in t:
        return "annexe3"
    return t[:80]


def _extract_remuneration_excerpt(text: str) -> str:
    """Extrait les articles / passages rémunération et prime d'ancienneté."""
    patterns = [
        r"(?is)(article\s+7\.1.{0,12000})(?=article\s+7\.2|article\s+8|\Z)",
        r"(?is)(article\s+7\.2.{0,8000})(?=article\s+7\.3|article\s+8|\Z)",
        r"(?is)(prime d['']ancienneté.{0,4000})",
        r"(?is)(prime d['']anciennete.{0,4000})",
        r"(?is)(titre v.{0,15000})(?=titre vi|\Z)",
    ]
    parts: list[str] = []
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            parts.append(m.group(1).strip())
    if parts:
        return "\n\n---\n\n".join(parts)
    idx = text.lower().find("salaires minimaux")
    if idx >= 0:
        return text[max(0, idx - 500) : idx + 8000]
    return text[:25_000]


def _text_len(lines: list[str]) -> int:
    return sum(len(x) for x in lines)


def _truncate(text: str) -> str:
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[:MAX_TEXT_CHARS] + "\n\n[...Document tronqué...]"


def get_kali_client() -> KaliClient:
    return KaliClient()
