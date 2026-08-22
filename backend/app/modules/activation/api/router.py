"""
Routers du module activation.

- router_public : /api/activation/* — SANS authentification. Toute erreur de
  jeton sort en 400 avec un message unique (pas d'énumération).
- router_rh : invitation depuis la fiche salarié (profil RH requis,
  périmètre société vérifié en application).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.activation.application import commands, queries
from app.modules.activation.schemas.requests import (
    ActivationCompleteRequest,
    ActivationVerifyRequest,
)
from app.modules.activation.schemas.responses import (
    ActivationCompleteResponse,
    ActivationVerifyResponse,
    InvitationSentResponse,
    InvitationStatusResponse,
)
from app.modules.employees.api.deps import require_rh_access
from app.modules.users.schemas.responses import User

router_public = APIRouter(prefix="/api/activation", tags=["activation"])
router_rh = APIRouter(prefix="/api/employees", tags=["activation"])


def _map_activation_error(exc: commands.ActivationError) -> HTTPException:
    if isinstance(exc, commands.InvalidTokenError):
        # Message unique, jamais de code détaillé côté public.
        return HTTPException(status_code=400, detail=exc.message)
    if isinstance(exc, commands.EmployeeNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(
        exc,
        (
            commands.EmailMissingError,
            commands.EmployeeInactiveError,
            commands.InvalidPasswordError,
        ),
    ):
        return HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.message}
        )
    return HTTPException(
        status_code=502, detail={"code": exc.code, "message": exc.message}
    )


# ----- Public -----


@router_public.post("/verify", response_model=ActivationVerifyResponse)
def verify_activation_route(request: ActivationVerifyRequest):
    """Jeton vivant → prénom + société. Sinon 400 générique."""
    try:
        return commands.verify_activation_token(request.token)
    except commands.ActivationError as exc:
        raise _map_activation_error(exc)


@router_public.post("/complete", response_model=ActivationCompleteResponse)
def complete_activation_route(request: ActivationCompleteRequest):
    """Choix du mot de passe : crée/relie le compte puis consomme le jeton."""
    try:
        return commands.complete_activation(request.token, request.password)
    except commands.ActivationError as exc:
        raise _map_activation_error(exc)


# ----- RH -----


@router_rh.post(
    "/{employee_id}/invitation", response_model=InvitationSentResponse
)
def invite_employee_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Invite (ou ré-invite) le salarié : nouvel e-mail, anciens jetons morts."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    try:
        return commands.invite_employee(
            employee_id, company_id, str(current_user.id)
        )
    except commands.ActivationError as exc:
        raise _map_activation_error(exc)


@router_rh.get(
    "/{employee_id}/invitation", response_model=InvitationStatusResponse
)
def invitation_status_route(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """État d'invitation de la fiche : jamais invité / invité le X / activé."""
    company_id = require_rh_access(current_user.active_company_id, current_user)
    try:
        return queries.get_invitation_status(employee_id, company_id)
    except commands.ActivationError as exc:
        raise _map_activation_error(exc)
