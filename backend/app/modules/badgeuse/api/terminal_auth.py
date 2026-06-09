"""Authentification des terminaux badgeuse kiosque."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Annotated, Deque, Dict

from fastapi import Header, HTTPException, Request, status

from app.modules.badgeuse.application.terminal_service import (
    TerminalContext,
    authenticate_terminal,
)

TERMINAL_TOKEN_HEADER = "X-Badgeuse-Terminal-Token"
SCAN_RATE_LIMIT = 30
SCAN_RATE_WINDOW_SECONDS = 60

_scan_attempts: Dict[str, Deque[float]] = defaultdict(deque)


def get_badgeuse_terminal_context(
    x_badgeuse_terminal_token: Annotated[
        str | None, Header(alias=TERMINAL_TOKEN_HEADER)
    ] = None,
) -> TerminalContext:
    ctx = authenticate_terminal(x_badgeuse_terminal_token)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton terminal invalide ou révoqué",
        )
    return ctx


def enforce_terminal_scan_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _scan_attempts[client_host]
    while bucket and now - bucket[0] > SCAN_RATE_WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= SCAN_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de scans. Réessayez dans une minute.",
        )
    bucket.append(now)
