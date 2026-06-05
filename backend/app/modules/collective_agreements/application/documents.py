"""Service de génération des documents PDF de convention collective.

Deux documents pour les RH d'une entreprise ayant la convention assignée :
- ``texte intégral`` : le texte KALI structuré rendu en PDF.
- ``synthèse`` : une synthèse pédagogique générée par IA (mise en cache).
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Optional

from app.modules.collective_agreements.application.service import (
    CollectiveAgreementsService,
    get_collective_agreements_service,
)
from app.modules.collective_agreements.domain.exceptions import (
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.modules.collective_agreements.infrastructure.document_pdf import (
    build_full_text_pdf,
    build_synthesis_pdf,
)
from app.modules.collective_agreements.infrastructure.providers import (
    AgreementTextCacheProvider,
)
from app.shared.infrastructure.ai import (
    MODEL_COLLECTIVE_AGREEMENT_CHAT,
    chat_completions_create,
)

logger = logging.getLogger(__name__)

DOC_FULL_TEXT = "full-text"
DOC_SYNTHESIS = "synthesis"

_MAX_SYNTHESIS_INPUT_CHARS = 150_000

_SYNTHESIS_SYSTEM_PROMPT = """Tu es un expert en droit du travail et en conventions collectives françaises.
Tu rédiges une synthèse pédagogique claire d'une convention collective à destination
de responsables RH (non juristes).

Règles :
- Base-toi UNIQUEMENT sur le texte fourni. N'invente rien.
- Si une information n'est pas présente, écris "Non précisé dans le texte fourni".
- Style clair, professionnel, accessible. Phrases courtes.
- Sortie en markdown simple : titres "##", sous-titres "###", listes "- ", gras "**".
- Pas de tableau complexe ; privilégie des listes lisibles.
- Cite les articles quand ils sont identifiables."""

_SYNTHESIS_SECTIONS = """Structure ta synthèse avec ces sections (omets celles absentes du texte) :

## Présentation générale
## Champ d'application
## Classification et coefficients
## Salaires minima
## Primes et indemnités
## Durée du travail
## Congés et absences
## Maladie, prévoyance
## Période d'essai et préavis
## Rupture du contrat
## Points de vigilance pour la paie

Termine par une courte note rappelant de vérifier la version en vigueur sur Légifrance."""


class CCDocumentService:
    """Génère les PDF (texte intégral, synthèse) avec contrôle d'accès RH."""

    def __init__(
        self,
        *,
        agreements: Optional[CollectiveAgreementsService] = None,
        text_cache: Optional[AgreementTextCacheProvider] = None,
        model: str = MODEL_COLLECTIVE_AGREEMENT_CHAT,
    ):
        self._agreements = agreements or get_collective_agreements_service()
        self._text_cache = text_cache or AgreementTextCacheProvider()
        self._model = model

    def get_document(
        self,
        agreement_id: str,
        doc_kind: str,
        *,
        company_id: Optional[str],
        has_rh_access: bool,
        is_platform_admin: bool,
    ) -> tuple[bytes, str]:
        """Retourne (pdf_bytes, filename) pour le document demandé."""
        if doc_kind not in (DOC_FULL_TEXT, DOC_SYNTHESIS):
            raise ValidationError(f"Type de document inconnu : {doc_kind}")

        agreement = self._agreements.get_catalog_item(agreement_id)
        if not agreement:
            raise NotFoundError("Convention collective non trouvée")

        self._ensure_access(
            agreement_id,
            company_id=company_id,
            has_rh_access=has_rh_access,
            is_platform_admin=is_platform_admin,
        )

        title = str(agreement.get("name") or "Convention collective").strip()
        idcc = str(agreement.get("idcc") or "").strip()
        full_text = self._load_full_text(agreement_id, agreement)

        if doc_kind == DOC_FULL_TEXT:
            pdf = build_full_text_pdf(title=title, idcc=idcc, full_text=full_text)
            return pdf, _filename(idcc, "texte-integral")

        synthesis = self._get_or_generate_synthesis(
            agreement_id, title=title, idcc=idcc, full_text=full_text
        )
        pdf = build_synthesis_pdf(title=title, idcc=idcc, synthesis_md=synthesis)
        return pdf, _filename(idcc, "synthese")

    def _ensure_access(
        self,
        agreement_id: str,
        *,
        company_id: Optional[str],
        has_rh_access: bool,
        is_platform_admin: bool,
    ) -> None:
        if is_platform_admin:
            return
        if not has_rh_access or not company_id:
            raise ForbiddenError("Accès non autorisé")
        if not self._agreements._repo.check_assignment_exists(
            company_id, agreement_id
        ):
            raise ForbiddenError(
                "Cette convention n'est pas assignée à votre entreprise"
            )

    def _load_full_text(self, agreement_id: str, agreement: dict) -> str:
        cached = self._text_cache.get_full_text(agreement_id)
        if cached:
            return cached
        if not agreement.get("rules_pdf_path"):
            raise ValidationError(
                "Aucun texte disponible — importez la convention depuis Légifrance "
                "ou uploadez un PDF (espace Super Admin)."
            )
        pdf_url = self._agreements._storage.create_signed_url(
            agreement["rules_pdf_path"], 3600
        )
        if not pdf_url:
            raise ValidationError("Impossible de générer l'URL du PDF source")
        return self._agreements._get_or_cache_pdf_text(
            agreement_id, pdf_url, agreement.get("name", "")
        )

    def _get_or_generate_synthesis(
        self,
        agreement_id: str,
        *,
        title: str,
        idcc: str,
        full_text: str,
    ) -> str:
        current_hash = _hash_text(full_text)
        meta = self._text_cache.get_text_with_meta(agreement_id)
        if (
            meta
            and meta.get("synthesis_md")
            and meta.get("synthesis_source_hash") == current_hash
        ):
            return str(meta["synthesis_md"])

        synthesis = self._generate_synthesis(title=title, idcc=idcc, full_text=full_text)
        if synthesis.strip():
            self._text_cache.set_synthesis(
                agreement_id,
                synthesis_md=synthesis,
                source_hash=current_hash,
                model=self._model,
            )
        return synthesis

    def _generate_synthesis(self, *, title: str, idcc: str, full_text: str) -> str:
        excerpt = full_text[:_MAX_SYNTHESIS_INPUT_CHARS]
        user_prompt = f"""Convention collective : {title} (IDCC {idcc}).

{_SYNTHESIS_SECTIONS}

Texte de la convention :
---
{excerpt}
---"""
        try:
            response = chat_completions_create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=4000,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Génération synthèse IDCC %s échouée", idcc)
            raise ValidationError(
                f"Génération de la synthèse impossible : {exc}"
            ) from exc


def _filename(idcc: str, suffix: str) -> str:
    safe_idcc = re.sub(r"[^0-9A-Za-z]", "", idcc) or "cc"
    return f"convention-{safe_idcc}-{suffix}.pdf"


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cc_document_service() -> CCDocumentService:
    return CCDocumentService()
