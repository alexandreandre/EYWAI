"""
Router API du module copilot.

Rôle strict : validation des entrées (schémas), auth (get_current_user), appel de l’application,
construction de la réponse HTTP, mapping des exceptions. Aucune logique métier.
Comportement HTTP identique à api/routers/copilot.py et api/routers/copilot_agent.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.copilot.api.dependencies import AuthenticatedUser
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

router = APIRouter(tags=["Copilot (Text-to-SQL)"])
router_agent = APIRouter(tags=["Copilot Agent"])


@router.post("/query", response_model=QueryResponse)
async def handle_query(
    request: QueryRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """POST /query : délègue à commands.execute_text_to_sql, retourne QueryResponse."""
    try:
        result = commands.execute_text_to_sql(
            TextToSqlInput(prompt=request.prompt, user_id=current_user.id)
        )
        return QueryResponse(
            answer=result.answer,
            sql_query=result.sql_query,
            data=result.data,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logging.error("Erreur dans le Copilote: %s", e, exc_info=True)
        detail = getattr(e, "message", str(e))
        raise HTTPException(status_code=500, detail=f"Erreur du Copilote: {detail}")


@router_agent.post("/query-agent", response_model=AgentResponse)
async def handle_agent_query(
    request: AgentRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
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
            )
        )
        return AgentResponse(
            answer=result.answer,
            needs_clarification=result.needs_clarification,
            clarification_question=result.clarification_question,
            sql_queries=result.sql_queries,
            data=result.data,
            thought_process=result.thought_process,
        )
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error("Erreur dans l'agent: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur de l'agent: {str(e)}")
