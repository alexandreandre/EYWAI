"""
Providers infrastructure : storage, cache texte, extraction PDF, chat LLM.

Implémentations réelles (Supabase storage, table collective_agreement_texts, OpenRouter).
"""

from __future__ import annotations
from app.core.logging import get_logger

logger = get_logger("modules.collective_agreements.infrastructure.providers")

import re
from io import BytesIO
from typing import Any, List, Optional

import pdfplumber
import requests

from app.core.database import get_supabase_client
from app.shared.infrastructure.ai import (
    MODEL_COLLECTIVE_AGREEMENT_CHAT,
    chat_completions_create,
)
from app.modules.collective_agreements.domain.exceptions import ValidationError

BUCKET_NAME = "collective_agreement_rules"
CHAT_MODEL = MODEL_COLLECTIVE_AGREEMENT_CHAT
MAX_TEXT_CHARS = 400000


class AgreementStorageProvider:
    """Implémentation de IAgreementStorageProvider (bucket collective_agreement_rules)."""

    def __init__(self, supabase_client: Any = None):
        self._supabase = supabase_client or get_supabase_client()

    def create_signed_url(self, path: str, ttl_seconds: int = 3600) -> Optional[str]:
        if not path:
            return None
        try:
            signed = self._supabase.storage.from_(BUCKET_NAME).create_signed_url(
                path, ttl_seconds
            )
            return signed.get("signedURL") if signed else None
        except Exception as e:
            logger.warning(f"[WARNING] Erreur lors de la génération de l'URL signée: {e}")
            return None

    def create_signed_upload_url(self, path: str) -> dict[str, str]:
        signed = self._supabase.storage.from_(BUCKET_NAME).create_signed_upload_url(
            path
        )
        if "signedUrl" not in signed:
            raise ValidationError(
                f"Erreur de stockage Supabase: clé 'signedUrl' non trouvée: {signed}"
            )
        return {"path": path, "signedUrl": signed["signedUrl"]}

    def remove(self, paths: List[str]) -> None:
        try:
            self._supabase.storage.from_(BUCKET_NAME).remove(paths)
        except Exception as e:
            logger.warning(f'[WARNING] Erreur lors de la suppression du PDF: {e}')


class AgreementTextCacheProvider:
    """Implémentation de IAgreementTextCache (table collective_agreement_texts)."""

    def __init__(self, supabase_client: Any = None):
        self._supabase = supabase_client or get_supabase_client()

    def get_full_text(self, agreement_id: str) -> Optional[str]:
        try:
            response = (
                self._supabase.table("collective_agreement_texts")
                .select("full_text")
                .eq("agreement_id", agreement_id)
                .maybe_single()
                .execute()
            )
            if response and response.data and response.data.get("full_text"):
                return response.data["full_text"]
        except Exception as e:
            logger.warning(f"[WARNING] Impossible d'accéder au cache: {e}")
        return None

    def get_text_with_meta(self, agreement_id: str) -> Optional[dict]:
        """Récupère texte + hash source + synthèse en cache (une requête)."""
        try:
            response = (
                self._supabase.table("collective_agreement_texts")
                .select(
                    "full_text, pdf_hash, synthesis_md, "
                    "synthesis_source_hash, synthesis_model"
                )
                .eq("agreement_id", agreement_id)
                .maybe_single()
                .execute()
            )
            if response and response.data:
                return dict(response.data)
        except Exception as e:
            logger.warning(f"[WARNING] Impossible d'accéder au cache (meta): {e}")
        return None

    def set_synthesis(
        self,
        agreement_id: str,
        *,
        synthesis_md: str,
        source_hash: str,
        model: str,
    ) -> None:
        """Met en cache la synthèse IA d'une convention."""
        from datetime import datetime, timezone

        payload = {
            "synthesis_md": synthesis_md,
            "synthesis_source_hash": source_hash,
            "synthesis_model": model,
            "synthesis_generated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._supabase.table("collective_agreement_texts").update(payload).eq(
                "agreement_id", agreement_id
            ).execute()
        except Exception as e:
            logger.warning(f"[WARNING] Impossible de sauvegarder la synthèse: {e}")

    def set_full_text(
        self,
        agreement_id: str,
        full_text: str,
        character_count: int,
        *,
        source_hash: str = "cached",
    ) -> None:
        cache_data = {
            "agreement_id": agreement_id,
            "full_text": full_text,
            "pdf_hash": source_hash,
            "character_count": character_count,
        }
        try:
            existing = (
                self._supabase.table("collective_agreement_texts")
                .select("agreement_id")
                .eq("agreement_id", agreement_id)
                .maybe_single()
                .execute()
            )
            if existing and existing.data:
                self._supabase.table("collective_agreement_texts").update(
                    cache_data
                ).eq("agreement_id", agreement_id).execute()
            else:
                self._supabase.table("collective_agreement_texts").insert(
                    cache_data
                ).execute()
        except Exception as e:
            logger.warning(f'[WARNING] Impossible de sauvegarder le cache: {e}')

    def get_base_text_char_count(self, agreement_id: str) -> int:
        """Taille du texte de base réellement stocké (0 si absent).

        Sert à relire après écriture : c'est la seule preuve qu'un backfill a
        abouti, l'API pouvant échouer en cours d'envoi.
        """
        try:
            reponse = (
                self._supabase.table("collective_agreement_texts")
                .select("base_text_char_count")
                .eq("agreement_id", agreement_id)
                .maybe_single()
                .execute()
            )
            if reponse and reponse.data:
                return int(reponse.data.get("base_text_char_count") or 0)
        except Exception as e:
            logger.warning(f"[WARNING] Relecture de base_text impossible: {e}")
        return 0

    def set_base_text(self, agreement_id: str, base_text: str) -> bool:
        """Met en cache le texte de base intégral (lu par l'assistant RH).

        Ne fait rien si le texte est vide : mieux vaut conserver le précédent
        rapatriement qu'écraser la convention par du vide en cas de sortie
        inattendue de KALI.

        Renvoie vrai si l'écriture a bien eu lieu. L'échec reste non bloquant
        pour la synchro mensuelle — un cache manquant ne doit pas la faire
        tomber — mais l'appelant DOIT pouvoir le savoir : un backfill qui
        annonce « écrit » sur une écriture perdue laisse une convention vide
        sans que personne ne s'en aperçoive (arrivé le 07/08 sur l'IDCC 0292,
        coupure SSL en cours d'envoi).
        """
        from datetime import datetime, timezone

        if not (base_text or "").strip():
            return False
        payload = {
            "base_text": base_text,
            "base_text_char_count": len(base_text),
            "base_text_updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._supabase.table("collective_agreement_texts").update(payload).eq(
                "agreement_id", agreement_id
            ).execute()
            return True
        except Exception as e:
            logger.warning(f"[WARNING] Impossible de sauvegarder le texte de base: {e}")
            return False

    def delete(self, agreement_id: str) -> None:
        self._supabase.table("collective_agreement_texts").delete().eq(
            "agreement_id", agreement_id
        ).execute()


class AgreementPdfTextExtractor:
    """Implémentation de IAgreementPdfTextExtractor (requests + pdfplumber)."""

    def extract(self, pdf_url: str) -> str:
        resp = requests.get(pdf_url, timeout=60)
        resp.raise_for_status()
        text_content = []
        with pdfplumber.open(BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text = re.sub(r"\s+", " ", text)
                    text_content.append(text.strip())
        return "\n\n".join(text_content)


class AgreementChatProvider:
    """Implémentation de IAgreementChatProvider (OpenRouter)."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key

    def answer(self, system_prompt: str, user_prompt: str) -> str:
        if self._api_key:
            from openai import OpenAI

            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self._api_key,
            )
            response = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
        else:
            response = chat_completions_create(
                model=MODEL_COLLECTIVE_AGREEMENT_CHAT,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
        return (response.choices[0].message.content or "").strip()
