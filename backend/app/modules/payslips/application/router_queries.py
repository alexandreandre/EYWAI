"""Requêtes exposées aux routers payslips (lecture seule)."""

from __future__ import annotations

from typing import Any

from app.modules.payslips.infrastructure.queries import get_payslip_meta as _get_payslip_meta


def get_payslip_meta_for_access(payslip_id: str) -> dict[str, Any] | None:
    return _get_payslip_meta(payslip_id)
