"""
Router API du module copilot.

Rôle strict : validation des entrées (schémas), auth (get_current_user), appel de l’application,
construction de la réponse HTTP, mapping des exceptions. Aucune logique métier.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from openai import APIConnectionError, AuthenticationError, RateLimitError

from app.modules.copilot.api.dependencies import require_copilot_rh_user
from app.modules.copilot.schemas import (
    AgentRequest,
    AgentResponse,
    QueryRequest,
    QueryResponse,
)
from app.modules.copilot.application import commands
from app.modules.copilot.application.dto import (
    AgentMessageDto,
    AgentQueryInput,
    TextToSqlInput,
)
from app.modules.copilot.domain.data_access import (
    COPILOT_DATA_UNAVAILABLE_MESSAGE,
    DataRetrievalDisabledError,
)
from app.modules.users.schemas.responses import User

router = APIRouter(tags=["Copilot (endpoint historique désactivé)"])
router_agent = APIRouter(tags=["Copilot Agent"])


@router.post("/query", response_model=QueryResponse)
def handle_query(
    request: QueryRequest,
    current_user: User = Depends(require_copilot_rh_user),
):
    """POST /query : endpoint historique définitivement indisponible (HTTP 503)."""
    try:
        result = commands.execute_text_to_sql(
            TextToSqlInput(
                prompt=request.prompt,
                user_id=current_user.id,
                active_company_id=current_user.active_company_id,
            )
        )
        return QueryResponse(answer=result.answer)
    except DataRetrievalDisabledError:
        raise HTTPException(
            status_code=503,
            detail=COPILOT_DATA_UNAVAILABLE_MESSAGE,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Entreprise active introuvable.")
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="Le Copilote ne peut pas traiter la demande.",
        )
    except (AuthenticationError, APIConnectionError, RateLimitError) as e:
        logging.warning(
            "Copilote : échec appel fournisseur LLM (%s)", type(e).__name__
        )
        raise HTTPException(
            status_code=502,
            detail="Le service d'IA est temporairement indisponible ou mal configuré.",
        )
    except Exception as e:
        logging.error("Erreur dans le Copilote: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Le Copilote ne peut pas traiter la demande.",
        )


@router_agent.post("/query-agent", response_model=AgentResponse)
def handle_agent_query(
    request: AgentRequest,
    current_user: User = Depends(require_copilot_rh_user),
):
    """POST /query-agent : délègue à commands.handle_agent_query, retourne AgentResponse."""
    try:
        history = [
            AgentMessageDto(role=m.role, content=m.content)
            for m in (request.conversation_history or [])
        ]
        result = commands.handle_agent_query(
            AgentQueryInput(
                prompt=request.prompt,
                conversation_history=history,
                user_id=current_user.id,
                active_company_id=current_user.active_company_id,
                # Le rôle vient du serveur, jamais du corps de la requête : il
                # décide du périmètre des outils nominatifs.
                user_role=current_user.get_role_in_company(
                    current_user.active_company_id or ""
                )
                or "",
            )
        )
        return AgentResponse(
            answer=result.answer,
            needs_clarification=result.needs_clarification,
            clarification_question=result.clarification_question,
        )
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="Le Copilote ne peut pas traiter la demande.",
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Entreprise active introuvable.")
    except (AuthenticationError, APIConnectionError, RateLimitError) as e:
        logging.warning(
            "Copilote agent : échec appel fournisseur LLM (%s)", type(e).__name__
        )
        raise HTTPException(
            status_code=502,
            detail="Le service d'IA est temporairement indisponible ou mal configuré.",
        )
    except Exception as e:
        logging.error("Erreur dans l'agent: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Le Copilote ne peut pas traiter la demande.",
        )
