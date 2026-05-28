"""
Router API du module support.

Délègue toute la logique à la couche application (commands, queries).
"""

from __future__ import annotations

import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.security import get_current_user
from app.modules.exports.api.dependencies import get_active_company_id
from app.modules.support.application import commands, queries
from app.modules.support.schemas.requests import TicketCreate, TicketStatusUpdate
from app.modules.support.schemas.responses import TicketResponse
from app.modules.users.schemas.responses import User

router = APIRouter(
    prefix="/api/support",
    tags=["Support"],
)


def _handle_application_errors(e: Exception) -> None:
    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(status_code=503, detail=str(e))
    raise


def _user_display_name(user: User) -> str:
    parts = [p for p in (user.first_name, user.last_name) if p]
    if parts:
        return " ".join(parts)
    return user.email or "Utilisateur"


def _company_name_for_active(user: User, active_company_id: str) -> str:
    for access in user.accessible_companies:
        if access.company_id == active_company_id:
            return access.company_name
    return ""


def _ticket_row_to_response(row: dict) -> TicketResponse:
    clean = {k: v for k, v in row.items() if k != "companies"}
    return TicketResponse.model_validate(clean)


@router.post("/tickets", response_model=TicketResponse, status_code=201)
async def post_ticket(
    body: TicketCreate,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Crée un ticket support (email puis persistance)."""
    try:
        created = commands.create_ticket(
            ticket_data=body.model_dump(),
            user_id=str(current_user.id),
            user_role=current_user.role,
            company_id=company_id,
            user_email=current_user.email or "",
            user_name=_user_display_name(current_user),
            company_name=_company_name_for_active(user=current_user, active_company_id=company_id),
        )
        return _ticket_row_to_response(created)
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail=(
                "L'envoi de votre demande a échoué. "
                "Vous pouvez contacter directement notre équipe à contact@eywai.fr."
            ),
        )
    except (ValueError, LookupError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickets", response_model=List[TicketResponse])
async def get_tickets(
    company_id: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    x_active_company: Optional[str] = Header(None, alias="X-Active-Company"),
):
    """Liste les tickets selon le rôle et les filtres."""
    try:
        filters: dict = {}
        if company_id is not None:
            filters["company_id"] = company_id
        if urgency is not None:
            filters["urgency"] = urgency
        if status is not None:
            filters["status"] = status
        if module is not None:
            filters["module"] = module
        if date_from is not None:
            filters["date_from"] = date_from
        if date_to is not None:
            filters["date_to"] = date_to
        if user_id is not None:
            filters["user_id"] = user_id

        if current_user.is_platform_admin:
            rows = queries.get_tickets_super_admin(filters)
        elif current_user.role in ("admin", "rh", "collaborateur_rh"):
            if not x_active_company:
                raise HTTPException(
                    status_code=400,
                    detail="X-Active-Company header is required",
                )
            rows = queries.get_tickets_for_company(x_active_company, filters)
        elif x_active_company and current_user.has_rh_access_in_company(
            x_active_company
        ):
            rows = queries.get_tickets_for_company(x_active_company, filters)
        else:
            rows = queries.get_tickets_for_user(str(current_user.id))

        return [_ticket_row_to_response(r) for r in rows]
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_user),
):
    """Détail d'un ticket avec historique de statuts."""
    try:
        ticket = queries.get_ticket_detail(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket introuvable.")

        ticket_company_id = ticket.get("company_id")
        if current_user.is_platform_admin:
            pass
        elif ticket_company_id is not None and current_user.has_rh_access_in_company(
            str(ticket_company_id)
        ):
            pass
        elif str(ticket.get("user_id")) == str(current_user.id):
            pass
        else:
            raise HTTPException(
                status_code=403,
                detail="Vous n'avez pas l'autorisation d'accéder à ce ticket.",
            )

        return _ticket_row_to_response(ticket)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/tickets/{ticket_id}/status", response_model=TicketResponse)
async def patch_ticket_status(
    ticket_id: str,
    status_update: TicketStatusUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour le statut d'un ticket (Super Admin uniquement)."""
    try:
        if not current_user.is_platform_admin:
            raise HTTPException(
                status_code=403,
                detail="Action réservée au Super Admin.",
            )
        updated = commands.update_ticket_status(
            ticket_id,
            status_update.status,
            str(current_user.id),
        )
        return _ticket_row_to_response(updated)
    except HTTPException:
        raise
    except (ValueError, LookupError, RuntimeError) as e:
        _handle_application_errors(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
