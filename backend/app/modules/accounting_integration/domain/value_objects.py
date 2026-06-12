"""Objets valeur pour l'intégration comptable."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TransmissionMode(str, Enum):
    MANUAL = "manual"
    API_QUADRA = "api_quadra"
    API_SAGE = "api_sage"
    API_PENNYLANE = "api_pennylane"
    SFTP = "sftp"


class TransmissionStatus(str, Enum):
    GENERATED = "generated"
    QUEUED = "queued"
    SENT = "sent"
    TRANSMITTED = "transmitted"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    MANUAL = "manual"
    FAILED = "failed"


def is_api_mode(mode: str) -> bool:
    return mode.startswith("api_")


@dataclass
class ConnectionTestResult:
    success: bool
    status: str
    message: str


@dataclass
class TransmissionResult:
    success: bool
    status: str
    message: str
    external_ref: Optional[str] = None
