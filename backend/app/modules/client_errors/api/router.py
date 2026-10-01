"""POST /api/client-errors — journal d'une erreur d'écran, authentifié, débit limité."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.security import get_current_user
from app.modules.client_errors.application.commands import (
    DebitClientErrorsDepasse,
    enregistrer_erreur_ecran,
)
from app.modules.client_errors.schemas.requests import ClientErrorIn
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/client-errors", tags=["ClientErrors"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def post_client_error(
    body: ClientErrorIn,
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        enregistrer_erreur_ecran(str(current_user.id), body.model_dump())
    except DebitClientErrorsDepasse:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de signalements. Réessayez dans une minute.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
