"""Client API PISTE / Légifrance (fond KALI — conventions collectives)."""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from app.modules.collective_agreements.rules.constants import (
    EXTENDED_SALARY_IDCC,
    MAX_PAYROLL_ANNEXES_DEFAULT,
    MAX_PAYROLL_ANNEXES_EXTENDED,
    MAX_SALARY_TEXTS_DEFAULT,
    MAX_SALARY_TEXTS_EXTENDED,
    MAX_SALARY_ZONES_MULTI,
    MULTI_ZONE_IDCC,
)

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 400_000
# Le texte de base d'une grande convention dépasse le plafond du corpus paie
# (la métallurgie 3248 fait ~406 000 caractères) : on lui donne le sien, sinon
# la fin de la convention serait coupée.
MAX_BASE_TEXT_CHARS = 1_200_000
MAX_ARTICLE_FETCHES = 250
# Avenants de catégorie joints au corpus RH. La plasturgie 0292 compte 69 textes
# attachés en vigueur ; une douzaine suffit à couvrir les catégories de
# personnel et les thèmes du contrat de travail.
MAX_HR_ANNEXES = 12
MIN_FETCHED_TEXT_CHARS = 200


@dataclass
class KaliConventionMeta:
    idcc: str
    kalicont_id: str
    title: str
    legifrance_url: str
    full_title: str = ""


@dataclass
class KaliFetchResult:
    meta: KaliConventionMeta
    full_text: str
    character_count: int
    sections_fetched: int
    articles_fetched: int
    # Texte de base intégral de la convention. ``full_text`` n'en garde qu'un
    # extrait rémunération (corpus paie) ; l'assistant RH a besoin du texte
    # entier — période d'essai, préavis, congés, classifications.
    base_text: str = ""


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
            f"# {meta.full_title or meta.title}",
            f"IDCC {meta.idcc}",
            f"Source : {meta.legifrance_url}",
            "",
        ]
        articles_fetched = 0
        sections_fetched = 0

        # 1. Textes Salaires récents (grilles € + coefficients)
        salary_blocks, af, sf = self._collect_salary_texts(top_sections, idcc=meta.idcc)
        parts.extend(salary_blocks)
        articles_fetched += af
        sections_fetched += sf

        # 2. Annexes classification (Textes Attachés)
        annex_blocks, af, sf = self._collect_payroll_annexes(top_sections, idcc=meta.idcc)
        parts.extend(annex_blocks)
        articles_fetched += af
        sections_fetched += sf

        # 3. Texte de base intégral, récupéré une seule fois : il alimente à la
        #    fois l'extrait rémunération (paie) et ``base_text`` (assistant RH).
        base_text, af, sf = self._collect_base_text(top_sections)
        articles_fetched += af
        sections_fetched += sf

        rem_excerpt = _extract_remuneration_excerpt(base_text) if base_text else ""
        if rem_excerpt:
            parts.append(f"## Rémunération (texte de base)\n\n{rem_excerpt}")

        if len(parts) <= 4 and base_text:
            # Fallback : texte de base en vigueur (comportement legacy)
            parts.append(base_text)

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
            base_text=(
                _truncate(base_text, MAX_BASE_TEXT_CHARS) if base_text else ""
            ),
        )

    def _collect_salary_texts(
        self, top_sections: list[Any], *, idcc: str = ""
    ) -> tuple[list[str], int, int]:
        blocks: list[str] = []
        articles = 0
        sections = 0
        idcc_norm = _normalize_idcc(idcc) if idcc else ""
        multi_zone = idcc_norm in MULTI_ZONE_IDCC

        for top in top_sections:
            if not _section_title_matches(top, "textes salaires"):
                continue
            subs = _filter_vigueur_sections(top.get("sections") or [])
            candidates = [s for s in subs if _is_salary_kalitext(s)]
            if multi_zone:
                selected = _pick_latest_salary_texts_by_zone(
                    candidates, max_zones=MAX_SALARY_ZONES_MULTI
                )
            else:
                selected = _pick_salary_texts(candidates, idcc=idcc_norm)
            for sub in selected:
                sections += 1
                text, af = self._fetch_subsection_text(sub)
                if text:
                    title = sub.get("title", "").strip()
                    blocks.append(f"## Texte salarial : {title}\n\n{text}")
                    articles += af
                time.sleep(0.12)
        return blocks, articles, sections

    def _collect_payroll_annexes(
        self, top_sections: list[Any], *, idcc: str = ""
    ) -> tuple[list[str], int, int]:
        blocks: list[str] = []
        articles = 0
        sections = 0
        seen: set[str] = set()
        max_annexes = _payroll_annex_limit(idcc)
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
                if len(seen) >= max_annexes:
                    break
        return blocks, articles, sections

    def _collect_base_text(self, top_sections: list[Any]) -> tuple[str, int, int]:
        """Récupère le texte de base en vigueur : ``(texte, articles, sections)``.

        Un seul rapatriement sert les deux usages — l'extrait rémunération du
        corpus paie et le texte intégral destiné à l'assistant RH.
        """
        base = _pick_base_section(top_sections)
        if not base:
            return "", 0, 0
        # Plafond propre au texte de base : à 400 000 caractères, le parcours
        # s'arrêtait au milieu de la métallurgie 3248 et perdait les titres IV
        # à X — contrat de travail, durée du travail, congés, rupture.
        # KALI renvoie plusieurs versions d'un même article : la version en
        # vigueur et celles qu'elle remplace (`etat: REMPLACE`). Pour l'assistant
        # RH, on ne garde que ce qui s'applique aujourd'hui — sans quoi il peut
        # citer un article périmé comme s'il était en vigueur.
        # Le corpus paie (`full_text`) n'est volontairement pas filtré ici : ce
        # serait un changement de son contenu, à valider séparément.
        text, articles = self._fetch_subsection_text(
            base,
            limite=MAX_BASE_TEXT_CHARS,
            versions_en_vigueur_seulement=True,
        )
        if not text:
            return "", articles, 0

        # Certaines conventions ne mettent PAS les règles RH dans le texte de
        # base : la plasturgie 0292 y écrit « la période d'essai est fixée dans
        # les avenants particuliers » (art. 8) et renvoie de même pour le
        # préavis (art. 28). Sans ces avenants, l'assistant cite le bon article
        # et reste incapable de donner la durée. On les ajoute au corpus RH.
        annexes, af, sf = self._collect_hr_annexes(top_sections)
        if annexes:
            text = text + "\n\n" + "\n\n".join(annexes)
            articles += af
        return text, articles, 1 + sf

    def _collect_hr_annexes(
        self, top_sections: list[Any]
    ) -> tuple[list[str], int, int]:
        """Avenants de catégorie et textes attachés portant des règles RH.

        Pendant RH de ``_collect_payroll_annexes``. La sélection est volontairement
        étroite : les « Textes Attachés » comptent des dizaines d'accords de
        formation, d'OPCA et de financement paritaire qui n'apprennent rien sur
        le contrat de travail et noieraient le corpus.
        """
        blocks: list[str] = []
        articles = 0
        sections = 0
        vus: set[str] = set()
        for top in top_sections:
            if not _section_title_matches(top, "textes attach"):
                continue
            for sub in _filter_vigueur_sections(top.get("sections") or []):
                titre = str(sub.get("title") or "")
                if not _is_hr_annex(titre):
                    continue
                cle = _annex_dedupe_key(titre)
                if cle in vus:
                    continue
                vus.add(cle)
                sections += 1
                texte, af = self._fetch_subsection_text(
                    sub, versions_en_vigueur_seulement=True
                )
                if texte:
                    blocks.append(f"## {titre.strip()}\n\n{texte}")
                    articles += af
                time.sleep(0.12)
                if len(vus) >= MAX_HR_ANNEXES:
                    break
        return blocks, articles, sections

    def _fetch_subsection_text(
        self,
        sub: dict[str, Any],
        *,
        limite: int = MAX_TEXT_CHARS,
        versions_en_vigueur_seulement: bool = False,
    ) -> tuple[str, int]:
        text_id = str(sub.get("id") or "")
        lines: list[str] = []
        options = {
            "limite": limite,
            "versions_en_vigueur_seulement": versions_en_vigueur_seulement,
        }
        if text_id.startswith("KALITEXT"):
            kali_text = self._post("consult/kaliText", {"id": text_id})
            if not kali_text:
                return "", 0
            articles = self._append_section_content(kali_text, lines, **options)
        else:
            articles = self._append_section_content(sub, lines, **options)
        return "\n".join(lines).strip(), articles

    def _append_section_content(
        self,
        section: dict[str, Any],
        lines: list[str],
        *,
        depth: int = 0,
        limite: int = MAX_TEXT_CHARS,
        versions_en_vigueur_seulement: bool = False,
    ) -> int:
        return self._append_section_text(
            section,
            lines,
            depth=depth,
            limite=limite,
            versions_en_vigueur_seulement=versions_en_vigueur_seulement,
        )

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

    def search_conventions_by_text(
        self, query: str, *, limit: int = 10
    ) -> list[KaliConventionMeta]:
        """Recherche des conventions KALI par mots-clés (ex. plasturgie, syntec)."""
        cleaned = query.strip()
        if len(cleaned) < 2:
            return []

        self.require_configured()
        data = self._post(
            "search",
            {
                "recherche": {
                    "fond": "KALI",
                    "champs": [
                        {
                            "typeChamp": "ALL",
                            "criteres": [
                                {
                                    "typeRecherche": "UN_DES_MOTS",
                                    "valeur": cleaned,
                                    "operateur": "ET",
                                }
                            ],
                        }
                    ],
                    "pageNumber": 1,
                    "pageSize": min(max(limit * 4, 20), 40),
                    "sort": "PERTINENCE",
                }
            },
        )
        if not data:
            return []

        rows = data.get("results") or []
        candidates: list[tuple[KaliConventionMeta, int]] = []
        seen_idcc: set[str] = set()

        for row in rows:
            if not isinstance(row, dict):
                continue
            kalicont_id = _extract_kalicont_id(row)
            if not kalicont_id:
                continue
            title = _extract_row_title(row)
            idcc = _extract_idcc_from_row(row, title)
            if not idcc or idcc in seen_idcc:
                continue
            if _is_secondary_kali_title(title):
                continue
            seen_idcc.add(idcc)
            display_title = _normalize_display_title(title, idcc)
            meta = KaliConventionMeta(
                idcc=idcc,
                kalicont_id=kalicont_id,
                title=display_title,
                legifrance_url=_legifrance_url(kalicont_id),
                full_title=title or display_title,
            )
            score = _score_convention_title(title, idcc) + _score_text_match(title, cleaned)
            candidates.append((meta, score))

        candidates.sort(key=lambda item: (-item[1], item[0].title))
        return [meta for meta, _ in candidates[:limit]]

    def _resolve_from_list(self, idcc: str) -> Optional[KaliConventionMeta]:
        data = self._post(
            "list/conventions",
            {
                "pageSize": 20,
                "pageNumber": 1,
                "idcc": idcc.lstrip("0") or idcc,
                "legalStatus": ["VIGUEUR", "VIGUEUR_DIFF"],
                "sort": "DATE_PUBLI_DESC",
            },
        )
        if not data:
            return None
        return self._pick_best_convention(data.get("results") or [], idcc)

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
                    "pageSize": 20,
                    "sort": "CHRONO_DATE_PUBLI",
                }
            },
        )
        if not data:
            return None
        return self._pick_best_convention(data.get("results") or [], idcc)

    def _pick_best_convention(
        self, rows: list[Any], idcc: str
    ) -> Optional[KaliConventionMeta]:
        candidates: list[tuple[str, str, int]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            kalicont_id = _extract_kalicont_id(row)
            if not kalicont_id:
                continue
            title = _extract_row_title(row)
            candidates.append((kalicont_id, title, _score_convention_title(title, idcc)))

        if not candidates:
            return None

        high_quality = [item for item in candidates if item[2] >= 80]
        if high_quality:
            kalicont_id, title, score = max(high_quality, key=lambda item: item[2])
        else:
            candidates.sort(key=lambda item: (-item[2], -len(item[1])))
            kalicont_id, title, score = candidates[0]

        if score < 40:
            for cont_id, _, cont_score in sorted(candidates, key=lambda item: -item[2])[:5]:
                cont_title = self._resolve_title_from_cont(cont_id)
                if not cont_title:
                    continue
                resolved_score = _score_convention_title(cont_title, idcc)
                if resolved_score > score:
                    kalicont_id, title, score = cont_id, cont_title, resolved_score
                    break

        if score < 20 or _is_secondary_kali_title(title):
            cont_title = self._resolve_title_from_cont(kalicont_id)
            if cont_title and _score_convention_title(cont_title, idcc) >= score:
                title = cont_title

        full_title = title
        display_title = _normalize_display_title(title, idcc)
        return KaliConventionMeta(
            idcc=_normalize_idcc(idcc),
            kalicont_id=kalicont_id,
            title=display_title,
            legifrance_url=_legifrance_url(kalicont_id),
            full_title=full_title,
        )

    def _resolve_title_from_cont(self, kalicont_id: str) -> Optional[str]:
        cont = self._post("consult/kaliCont", {"id": kalicont_id})
        if not cont:
            return None
        cont_data = cont.get("conteneur") or cont
        title = cont_data.get("title") or cont_data.get("titre")
        if not title:
            return None
        return str(title).strip()

    def _append_section_text(
        self,
        section: dict[str, Any],
        lines: list[str],
        *,
        depth: int,
        limite: int = MAX_TEXT_CHARS,
        versions_en_vigueur_seulement: bool = False,
    ) -> int:
        articles_fetched = 0
        prefix = "#" * min(2 + depth, 4)
        title = section.get("title") or section.get("titre")
        if title:
            lines.append(f"\n{prefix} {title}\n")

        for article in section.get("articles") or []:
            if articles_fetched >= MAX_ARTICLE_FETCHES:
                break
            if versions_en_vigueur_seulement and not _article_en_vigueur(article):
                continue
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
            if _text_len(lines) >= limite:
                break
            articles_fetched += self._append_section_text(
                sub,
                lines,
                depth=depth + 1,
                limite=limite,
                versions_en_vigueur_seulement=versions_en_vigueur_seulement,
            )
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


_IDCC_IN_TITLE_RE = re.compile(r"(?i)\bidcc\s*(\d{1,4})\b")


def _extract_idcc_from_row(row: dict[str, Any], title: str = "") -> Optional[str]:
    for key in ("idcc", "numIdcc", "num"):
        val = row.get(key)
        if val is None:
            continue
        raw = str(val).strip()
        if raw.isdigit():
            return _normalize_idcc(raw)
    resolved_title = title or _extract_row_title(row)
    match = _IDCC_IN_TITLE_RE.search(resolved_title)
    if match:
        return _normalize_idcc(match.group(1))
    return None


def _score_text_match(title: str, query: str) -> int:
    from app.modules.collective_agreements.domain.search import (
        normalize_search_text,
        search_tokens,
    )

    normalized_title = normalize_search_text(title)
    score = 0
    for token in search_tokens(query):
        if token in normalized_title:
            score += 30
        if normalized_title.startswith(token):
            score += 20
    return score


def _extract_row_title(row: dict[str, Any]) -> str:
    titles = row.get("titles") or []
    if titles and isinstance(titles[0], dict):
        title = titles[0].get("title")
        if title:
            return str(title).strip()
    for key in ("titre", "title"):
        val = row.get(key)
        if val:
            return str(val).strip()
    return ""


def _score_convention_title(title: str, idcc: str) -> int:
    t = title.lower()
    score = 0
    if "convention collective" in t:
        score += 100
    elif t.startswith("convention "):
        score += 60
    if f"idcc {idcc.lstrip('0')}" in t or f"idcc {idcc}" in t:
        score += 40
    if idcc.lstrip("0") in t and "idcc" in t:
        score += 20
    if t.startswith("adhésion") or t.startswith("adhesion"):
        score -= 90
    if t.startswith("accord ") or " accord du " in t:
        score -= 70
    if t.startswith("avenant"):
        score -= 50
    if "lettre du" in t or "lettre de" in t:
        score -= 40
    if t.startswith("arrêté") or t.startswith("arrete"):
        score -= 60
    if "protocole" in t:
        score -= 30
    if "dénonciation" in t or "denonciation" in t:
        score -= 40
    return score


def _is_secondary_kali_title(title: str) -> bool:
    return _score_convention_title(title, "") < 20


def _normalize_display_title(title: str, idcc: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    if not cleaned or _is_secondary_kali_title(cleaned):
        return f"Convention collective IDCC {_normalize_idcc(idcc)}"
    return _shorten_catalog_display_title(cleaned)


def _shorten_catalog_display_title(title: str) -> str:
    """Intitulé court catalogue : tronque extensions légales après le titre principal."""
    patterns = (
        r"\s*\(c['']est",
        r"\s*\(occupant",
        r"\.\s*[ÉE]tendue par",
        r"\.\s*Elle s['']applique",
        r"\.\s*Dans sa rédaction",
    )
    for pat in patterns:
        match = re.search(pat, title, re.IGNORECASE)
        if match:
            return title[: match.start()].strip()
    return title


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
    return any(
        k in title
        for k in (
            "salaire",
            "rémunération",
            "remuneration",
            "classification",
            "positionnement",
            "valeur du point",
            "valeur de point",
            "minima",
            "grille",
            "barème",
            "bareme",
        )
    )


def _is_hr_annex(title: str) -> bool:
    """Vrai pour un texte attaché portant des règles du contrat de travail.

    Deux filtres successifs : on écarte d'abord les thèmes qui encombrent sans
    rien apporter (formation, OPCA, financement paritaire, adhésions,
    dénonciations), puis on ne retient que les avenants de catégorie et les
    textes traitant explicitement d'un sujet RH.
    """
    t = title.lower()
    exclus = (
        "formation professionnelle",
        "opca",
        "opco",
        "cqp",
        "observatoire",
        "financement",
        "fonctionnement",
        "apprentis",
        "lettre d'adhésion",
        "adhésion",
        "dénonciation",
        "création d'un",
        "activité réduite",
        "prévoyance",
        "retraite complémentaire",
    )
    if any(k in t for k in exclus):
        return False
    categories = (
        "ouvriers",
        "collaborateurs",
        "employés",
        "techniciens",
        "agents de maîtrise",
        "encadrement",
        "cadres",
        "mensuel",
    )
    themes = (
        "période d'essai",
        "periode d'essai",
        "préavis",
        "preavis",
        "licenciement",
        "rupture",
        "congés",
        "conges",
        "durée du travail",
        "duree du travail",
        "temps de travail",
        "ancienneté",
        "anciennete",
        "maladie",
        "maternité",
    )
    return any(k in t for k in categories) or any(k in t for k in themes)


def _is_payroll_annex(title: str) -> bool:
    t = title.lower()
    if "annexe" not in t and "classification" not in t and "grille" not in t:
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
            "ouvrier",
            "employé",
            "employe",
            "positionnement",
            "valeur du point",
            "valeur de point",
            "coefficient",
            "niveau",
        )
    )


def _is_extended_salary_idcc(idcc: str) -> bool:
    norm = _normalize_idcc(idcc)
    stripped = norm.lstrip("0") or "0"
    return norm in EXTENDED_SALARY_IDCC or stripped in {
        x.lstrip("0") for x in EXTENDED_SALARY_IDCC
    }


def _salary_text_limit(idcc: str) -> int:
    return MAX_SALARY_TEXTS_EXTENDED if _is_extended_salary_idcc(idcc) else MAX_SALARY_TEXTS_DEFAULT


def _payroll_annex_limit(idcc: str) -> int:
    return (
        MAX_PAYROLL_ANNEXES_EXTENDED
        if _is_extended_salary_idcc(idcc)
        else MAX_PAYROLL_ANNEXES_DEFAULT
    )


def _pick_salary_texts(
    candidates: list[dict[str, Any]], *, idcc: str
) -> list[dict[str, Any]]:
    """Garde les textes salariaux les plus récents (par année dans le titre)."""
    if not candidates:
        return []
    limit = _salary_text_limit(idcc)
    ordered = sorted(
        candidates,
        key=lambda s: _title_year(str(s.get("title") or "")),
        reverse=True,
    )
    return ordered[:limit]


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


def _title_year(title: str) -> int:
    years = [int(y) for y in re.findall(r"(20\d{2})", title)]
    return max(years) if years else 0


def _salary_zone_key_from_title(title: str) -> str:
    """Clé de déduplication géographique depuis le titre KALITEXT."""
    cleaned = re.sub(r"\s+", " ", str(title or "").strip())
    if " - " in cleaned:
        return cleaned.rsplit(" - ", 1)[-1].strip().lower()
    for marker in (
        "pour la ",
        "pour le ",
        "département ",
        "departement ",
        "région ",
        "region ",
    ):
        idx = cleaned.lower().find(marker)
        if idx >= 0:
            tail = cleaned[idx + len(marker) : idx + len(marker) + 60]
            return tail.split(",")[0].split("(")[0].strip().lower()
    return cleaned.lower()[:80]


def _pick_latest_salary_texts_by_zone(
    candidates: list[dict[str, Any]], *, max_zones: int
) -> list[dict[str, Any]]:
    """Garde le texte salarial le plus récent par zone géographique."""
    by_zone: dict[str, dict[str, Any]] = {}
    for sub in candidates:
        title = str(sub.get("title") or "")
        key = _salary_zone_key_from_title(title)
        year = _title_year(title)
        prev = by_zone.get(key)
        if not prev or year >= _title_year(str(prev.get("title") or "")):
            by_zone[key] = sub
    ordered = sorted(
        by_zone.values(),
        key=lambda s: _title_year(str(s.get("title") or "")),
        reverse=True,
    )
    return ordered[:max_zones]


def _article_en_vigueur(article: dict[str, Any], maintenant_ms: int | None = None) -> bool:
    """Vrai si cette version d'article s'applique aujourd'hui.

    KALI expose chaque version avec son ``etat`` (``VIGUEUR``, ``VIGUEUR_ETEN``,
    ``REMPLACE``, ``ABROGE``…) et ses bornes ``dateDebut`` / ``dateFin`` en
    millisecondes. Une version remplacée reste présente dans la réponse : sans
    filtre, elle se retrouve dans le texte au même titre que la version
    applicable. Un ``etat`` absent est considéré en vigueur (on ne retire pas un
    article faute de métadonnée).
    """
    etat = str(article.get("etat") or "").upper()
    if etat and not etat.startswith("VIGUEUR"):
        return False
    if maintenant_ms is None:
        maintenant_ms = int(time.time() * 1000)
    fin = article.get("dateFin")
    try:
        if fin is not None and int(fin) < maintenant_ms:
            return False
    except (TypeError, ValueError):
        pass
    return True


def _truncate(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[...Document tronqué...]"


def get_kali_client() -> KaliClient:
    return KaliClient()
