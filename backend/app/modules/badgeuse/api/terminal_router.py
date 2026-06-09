"""API publique (jeton terminal) pour la badgeuse kiosque."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.modules.badgeuse.api.terminal_auth import (
    TerminalContext,
    enforce_terminal_scan_rate_limit,
    get_badgeuse_terminal_context,
)
from app.modules.badgeuse.application import service as badgeuse_service
from app.modules.badgeuse.domain.time_tracking import TimeEntrySource

router_terminal = APIRouter(
    prefix="/api/badgeuse/terminal",
    tags=["Badgeuse - Terminal"],
)


@router_terminal.get("/status")
def get_terminal_status(
    ctx: TerminalContext = Depends(get_badgeuse_terminal_context),
) -> Dict[str, Any]:
    from app.core.database import supabase

    company_name = None
    logo_url = None
    try:
        row = (
            supabase.table("companies")
            .select("name, logo_url")
            .eq("id", ctx.company_id)
            .maybe_single()
            .execute()
        )
        if row.data:
            company_name = row.data.get("name")
            logo_url = row.data.get("logo_url")
    except Exception:
        pass
    return {
        "device_id": ctx.device_id,
        "company_id": ctx.company_id,
        "company_name": company_name,
        "logo_url": logo_url,
        "label": ctx.label,
        "ok": True,
    }


@router_terminal.get("/dashboard/today")
def get_terminal_dashboard_today(
    ctx: TerminalContext = Depends(get_badgeuse_terminal_context),
) -> Dict[str, Any]:
    return badgeuse_service.get_dashboard_today(company_id=ctx.company_id)


@router_terminal.get("/punch-candidates")
def list_terminal_punch_candidates(
    q: str | None = Query(None, description="Recherche nom ou identifiant"),
    only_not_badged: bool = Query(
        False, description="Uniquement les employés sans pointage aujourd'hui"
    ),
    limit: int = Query(24, ge=1, le=50),
    ctx: TerminalContext = Depends(get_badgeuse_terminal_context),
) -> List[Dict[str, Any]]:
    return badgeuse_service.list_punch_candidates(
        company_id=ctx.company_id,
        search=q,
        only_not_badged_today=only_not_badged,
        limit=limit,
    )


@router_terminal.post("/scan")
def terminal_scan_badge(
    payload: Dict[str, Any],
    request: Request,
    ctx: TerminalContext = Depends(get_badgeuse_terminal_context),
) -> Dict[str, Any]:
    enforce_terminal_scan_rate_limit(request)
    try:
        if payload.get("username"):
            return badgeuse_service.punch_by_username(
                username=str(payload["username"]),
                company_id=ctx.company_id,
                actor_user_id=ctx.device_id,
                terminal_device_id=ctx.device_id,
            )
        manual = bool(payload.get("employee_id")) and not payload.get("qr_payload")
        return badgeuse_service.punch_from_qr(
            qr_payload=payload.get("qr_payload"),
            employee_id=payload.get("employee_id"),
            company_id=ctx.company_id,
            actor_user_id=ctx.device_id,
            source=TimeEntrySource.RH if manual else TimeEntrySource.QR_SCAN,
            terminal_device_id=ctx.device_id,
        )
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail=str(e)) from e
