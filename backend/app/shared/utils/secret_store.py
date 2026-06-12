"""Stockage chiffré de secrets (credentials intégrations). Write-only côté API."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Dict, Optional

from app.core import settings


def _fernet_key() -> bytes:
    """Dérive une clé Fernet 32 octets depuis SECRET_ENCRYPTION_KEY ou SUPABASE_KEY."""
    raw = os.getenv("SECRET_ENCRYPTION_KEY") or getattr(settings, "SUPABASE_KEY", "") or "eywai-dev-fallback"
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(payload: Dict[str, Any]) -> str:
    """Chiffre un dict credentials → chaîne stockée dans credentials_ref."""
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_fernet_key())
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return f.encrypt(data).decode("ascii")
    except ImportError:
        # Repli dev sans cryptography : encodage base64 (non sécurisé, dev uniquement)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return "b64:" + base64.urlsafe_b64encode(data).decode("ascii")


def decrypt_secret(ref: Optional[str]) -> Optional[Dict[str, Any]]:
    """Déchiffre credentials_ref — usage interne connecteurs uniquement."""
    if not ref or not ref.strip():
        return None
    if ref.startswith("b64:"):
        try:
            raw = base64.urlsafe_b64decode(ref[4:].encode("ascii"))
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    try:
        from cryptography.fernet import Fernet

        f = Fernet(_fernet_key())
        raw = f.decrypt(ref.encode("ascii"))
        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def has_stored_secret(ref: Optional[str]) -> bool:
    return bool(ref and ref.strip())
