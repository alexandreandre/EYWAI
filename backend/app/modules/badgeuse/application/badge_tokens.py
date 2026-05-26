"""
Génération et validation des payloads QR badgeuse (HMAC signé).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import uuid
from dataclasses import dataclass
from typing import Optional

QR_PREFIX = "eywai:badge:v1"
_PAYLOAD_RE = re.compile(
    r"^eywai:badge:v1:([^:]+):([^:]+):(\d+):([A-Za-z0-9_-]+)$"
)


@dataclass(frozen=True)
class ParsedBadgeQr:
    company_id: str
    employee_id: str
    token_version: int


def _qr_secret() -> bytes:
    raw = os.environ.get("BADGEUSE_QR_SECRET", "eywai-badgeuse-dev-secret")
    return raw.encode("utf-8")


def _signing_key(secret_salt: str) -> bytes:
    return hashlib.sha256(_qr_secret() + secret_salt.encode("utf-8")).digest()


def compute_signature(
    *,
    company_id: str,
    employee_id: str,
    token_version: int,
    secret_salt: str,
) -> str:
    message = f"{company_id}:{employee_id}:{token_version}".encode("utf-8")
    digest = hmac.new(_signing_key(secret_salt), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:12]).decode("ascii").rstrip("=")


def build_qr_payload(
    *,
    company_id: str,
    employee_id: str,
    token_version: int,
    secret_salt: str,
) -> str:
    sig = compute_signature(
        company_id=company_id,
        employee_id=employee_id,
        token_version=token_version,
        secret_salt=secret_salt,
    )
    return f"{QR_PREFIX}:{company_id}:{employee_id}:{token_version}:{sig}"


def parse_qr_payload(payload: str) -> Optional[ParsedBadgeQr]:
    payload = (payload or "").strip()
    match = _PAYLOAD_RE.match(payload)
    if not match:
        return None
    company_id, employee_id, version_str, _sig = match.groups()
    try:
        token_version = int(version_str)
    except ValueError:
        return None
    if token_version < 1:
        return None
    return ParsedBadgeQr(
        company_id=company_id,
        employee_id=employee_id,
        token_version=token_version,
    )


def verify_qr_payload(
    payload: str,
    *,
    secret_salt: str,
    expected_version: int,
) -> Optional[ParsedBadgeQr]:
    parsed = parse_qr_payload(payload)
    if not parsed or parsed.token_version != expected_version:
        return None
    expected_sig = compute_signature(
        company_id=parsed.company_id,
        employee_id=parsed.employee_id,
        token_version=parsed.token_version,
        secret_salt=secret_salt,
    )
    parts = payload.strip().split(":")
    if len(parts) < 6:
        return None
    provided_sig = parts[-1]
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None
    return parsed


def new_secret_salt() -> str:
    return str(uuid.uuid4())
