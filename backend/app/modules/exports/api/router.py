# Router exports — délégation à la couche application uniquement.
# Comportement HTTP identique à api/routers/exports.py (prefix=/api/exports).
import traceback
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User
from app.modules.exports.api.dependencies import get_active_company_id
from app.modules.exports.application import service as export_service
from app.modules.exports.schemas import (
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportGenerateRequest,
    ExportGenerateResponse,
    ExportHistoryResponse,
    DSNGenerateResponse,
)

router = APIRouter(
    prefix="/api/exports",
    tags=["Exports"],
)


def _value_error_to_http(e: ValueError) -> HTTPException:
    """Traduit les ValueError du service en HTTPException (400 ou 404)."""
    msg = str(e)
    if "non trouvé" in msg.lower() or "aucun fichier" in msg.lower():
        return HTTPException(status_code=404, detail=msg)
    return HTTPException(status_code=400, detail=msg)


@router.post("/preview", response_model=ExportPreviewResponse)
async def preview_export(
    request: ExportPreviewRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Prévisualise un export sans générer de fichier."""
    try:
        return export_service.preview_export(company_id, request)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=Union[ExportGenerateResponse, DSNGenerateResponse])
async def generate_export(
    request: ExportGenerateRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Génère un export et retourne les fichiers."""
    try:
        return export_service.generate_export(company_id, current_user.id, request)
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history", response_model=ExportHistoryResponse)
async def get_export_history(
    export_type: Optional[str] = None,
    period: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Récupère l'historique des exports."""
    try:
        return export_service.get_export_history(company_id, export_type, period)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{export_id}")
async def download_export(
    export_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Télécharge un export depuis l'historique (retourne l'URL signée du premier fichier)."""
    try:
        download_url = export_service.get_export_download_url(company_id, export_id)
        return {"download_url": download_url}
    except ValueError as e:
        raise _value_error_to_http(e)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
