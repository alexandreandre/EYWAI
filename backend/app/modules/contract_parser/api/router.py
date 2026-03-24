"""
Router API du module contract_parser.

Préfixe et routes identiques à api/routers/contract_parser.py.
Délègue uniquement à la couche application (commands). Aucune logique métier ici.

Dépendances externes au module (toutes sous app/*) :
- app.core.security : get_current_user (auth transverse).
- app.modules.users.schemas.responses : User (type du contexte auth, contrat inter-module).
"""
import traceback

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.security import get_current_user
from app.modules.contract_parser.application import commands
from app.modules.contract_parser.schemas.responses import (
    ContractExtractionResponse,
    QuestionnaireExtractionResponse,
    RIBExtractionResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/contract-parser", tags=["Contract Parser"])


def _validate_pdf_file(file: UploadFile) -> None:
    """Validation entrée : fichier PDF requis. Lève HTTPException sinon."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format PDF.")


@router.post("/extract-from-pdf", response_model=ContractExtractionResponse)
async def extract_contract_from_pdf_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Extrait les informations d'un contrat de travail PDF (texte + LLM).
    """
    _validate_pdf_file(file)
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Le fichier PDF est vide.")
    try:
        result = commands.extract_contract_from_pdf(content)
        return ContractExtractionResponse(
            extracted_data=result.extracted_data,
            confidence=result.confidence,
            warnings=result.warnings,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'extraction : {str(e)}",
        )


@router.post("/extract-rib-from-pdf", response_model=RIBExtractionResponse)
async def extract_rib_from_pdf_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Extrait les informations bancaires (RIB) d'un PDF.
    """
    _validate_pdf_file(file)
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Le fichier PDF est vide.")
    try:
        result = commands.extract_rib_from_pdf(content)
        return RIBExtractionResponse(
            extracted_data=result.extracted_data,
            confidence=result.confidence,
            warnings=result.warnings,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'extraction du RIB : {str(e)}",
        )


@router.post("/extract-questionnaire-from-pdf", response_model=QuestionnaireExtractionResponse)
async def extract_questionnaire_from_pdf_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Extrait les informations d'un questionnaire d'embauche PDF.
    """
    _validate_pdf_file(file)
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Le fichier PDF est vide.")
    try:
        result = commands.extract_questionnaire_from_pdf(content)
        return QuestionnaireExtractionResponse(
            extracted_data=result.extracted_data,
            confidence=result.confidence,
            warnings=result.warnings,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de l'extraction du questionnaire : {str(e)}",
        )
