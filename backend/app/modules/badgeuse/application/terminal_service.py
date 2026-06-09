"""Gestion des terminaux badgeuse kiosque."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.badgeuse.domain.terminal_tokens import (
    MAX_ACTIVE_TERMINALS_PER_COMPANY,
    GeneratedTerminalToken,
    generate_terminal_token,
    hash_terminal_token,
)
from app.modules.badgeuse.infrastructure.terminal_devices_repository import (
    TerminalDevicesRepository,
)

_terminal_devices_repository = TerminalDevicesRepository()


@dataclass(frozen=True)
class TerminalContext:
    device_id: str
    company_id: str
    label: str


def list_terminal_devices(*, company_id: str) -> List[Dict[str, Any]]:
    rows = _terminal_devices_repository.list_devices(company_id)
    return [
        {
            "id": str(row["id"]),
            "company_id": str(row["company_id"]),
            "label": row.get("label") or "",
            "token_prefix": row.get("token_prefix") or "",
            "created_by": str(row.get("created_by") or ""),
            "last_used_at": row.get("last_used_at"),
            "revoked_at": row.get("revoked_at"),
            "created_at": row.get("created_at"),
            "is_active": not row.get("revoked_at"),
        }
        for row in rows
    ]


def activate_terminal_device_here(
    *,
    company_id: str,
    created_by: str,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Enregistre l'appareil courant comme terminal badgeuse (activation en un clic)."""
    clean_label = (label or "").strip()
    if not clean_label:
        clean_label = f"Appareil · {date.today().strftime('%d/%m/%Y')}"
    return create_terminal_device(
        company_id=company_id,
        label=clean_label,
        created_by=created_by,
    )


def create_terminal_device(
    *,
    company_id: str,
    label: str,
    created_by: str,
) -> Dict[str, Any]:
    clean_label = (label or "").strip()
    if not clean_label:
        raise ValueError("Le libellé du terminal est obligatoire")

    active_count = _terminal_devices_repository.count_active(company_id)
    if active_count >= MAX_ACTIVE_TERMINALS_PER_COMPANY:
        raise ValueError(
            f"Maximum de {MAX_ACTIVE_TERMINALS_PER_COMPANY} terminaux actifs atteint"
        )

    generated: GeneratedTerminalToken = generate_terminal_token()
    row = _terminal_devices_repository.create_device(
        company_id=company_id,
        label=clean_label,
        token_hash=generated.token_hash,
        token_prefix=generated.token_prefix,
        created_by=created_by,
    )
    return {
        "device": {
            "id": str(row["id"]),
            "company_id": str(row["company_id"]),
            "label": row.get("label") or "",
            "token_prefix": generated.token_prefix,
            "created_at": row.get("created_at"),
            "is_active": True,
        },
        "token": generated.raw_token,
    }


def revoke_terminal_device(*, device_id: str, company_id: str) -> None:
    _terminal_devices_repository.revoke_device(
        device_id=device_id,
        company_id=company_id,
    )


def authenticate_terminal(raw_token: Optional[str]) -> Optional[TerminalContext]:
    token = (raw_token or "").strip()
    if not token:
        return None
    row = _terminal_devices_repository.get_by_token_hash(hash_terminal_token(token))
    if not row or row.get("revoked_at"):
        return None
    device_id = str(row["id"])
    _terminal_devices_repository.touch_last_used(device_id)
    return TerminalContext(
        device_id=device_id,
        company_id=str(row["company_id"]),
        label=str(row.get("label") or ""),
    )
