"""Génération et validation des jetons terminal badgeuse."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass


MAX_ACTIVE_TERMINALS_PER_COMPANY = 5
TOKEN_BYTE_LENGTH = 32


@dataclass(frozen=True)
class GeneratedTerminalToken:
    raw_token: str
    token_hash: str
    token_prefix: str


def generate_terminal_token() -> GeneratedTerminalToken:
    raw = secrets.token_urlsafe(TOKEN_BYTE_LENGTH)
    return GeneratedTerminalToken(
        raw_token=raw,
        token_hash=hash_terminal_token(raw),
        token_prefix=raw[:8],
    )


def hash_terminal_token(raw_token: str) -> str:
    normalized = (raw_token or "").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
