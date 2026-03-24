"""
Providers infrastructure : storage, cache texte, extraction PDF, chat LLM.

Implémentations réelles (Supabase storage, table collective_agreement_texts, OpenAI).
"""
from __future__ import annotations

import os
import re
from io import BytesIO
from typing import Any, List, Optional

import pdfplumber
import requests
from openai import OpenAI

from app.core.database import get_supabase_client
from app.modules.collective_agreements.domain.exceptions import ValidationError

BUCKET_NAME = "collective_agreement_rules"
CHAT_MODEL = "gpt-4o-mini"
MAX_TEXT_CHARS = 400000


class AgreementStorageProvider:
    """Implémentation de IAgreementStorageProvider (bucket collective_agreement_rules)."""

    def __init__(self, supabase_client: Any = None):
        self._supabase = supabase_client or get_supabase_client()

    def create_signed_url(self, path: str, ttl_seconds: int = 3600) -> Optional[str]:
        try:
            signed = self._supabase.storage.from_(BUCKET_NAME).create_signed_url(path, ttl_seconds)
            return signed.get("signedURL") if signed else None
        except Exception as e:
            print(f"[WARNING] Erreur lors de la génération de l'URL signée: {e}")
            return None

    def create_signed_upload_url(self, path: str) -> dict[str, str]:
        signed = self._supabase.storage.from_(BUCKET_NAME).create_signed_upload_url(path)
        if "signedUrl" not in signed:
            raise ValidationError(
                f"Erreur de stockage Supabase: clé 'signedUrl' non trouvée: {signed}"
            )
        return {"path": path, "signedUrl": signed["signedUrl"]}

    def remove(self, paths: List[str]) -> None:
        try:
            self._supabase.storage.from_(BUCKET_NAME).remove(paths)
        except Exception as e:
            print(f"[WARNING] Erreur lors de la suppression du PDF: {e}")


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
            if response.data and response.data.get("full_text"):
                return response.data["full_text"]
        except Exception as e:
            print(f"[WARNING] Impossible d'accéder au cache: {e}")
        return None

    def set_full_text(
        self, agreement_id: str, full_text: str, character_count: int
    ) -> None:
        cache_data = {
            "agreement_id": agreement_id,
            "full_text": full_text,
            "pdf_hash": "cached",
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
                self._supabase.table("collective_agreement_texts").update(cache_data).eq(
                    "agreement_id", agreement_id
                ).execute()
            else:
                self._supabase.table("collective_agreement_texts").insert(cache_data).execute()
        except Exception as e:
            print(f"[WARNING] Impossible de sauvegarder le cache: {e}")

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
    """Implémentation de IAgreementChatProvider (OpenAI gpt-4o-mini)."""

    def __init__(self, api_key: Optional[str] = None):
        self._client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def answer(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        return (response.choices[0].message.content or "").strip()
