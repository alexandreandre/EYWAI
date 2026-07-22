"""
Dispatch fermé des outils Copilot.

``execute_tool`` est la SEULE façon d'exécuter un outil validé. Le mapping est
explicite et exhaustif : aucun import dynamique, aucun ``getattr`` sur une
entrée LLM, aucune chaîne SQL / nom de table / requête issue du modèle.

Le ``company_id`` transmis à la requête sécurisée est TOUJOURS celui du serveur
(argument positionnel), jamais une valeur fournie par le LLM.
"""

from __future__ import annotations

from typing import Any, Callable

from app.modules.copilot.domain.tools import ToolCall, ToolName
from app.modules.copilot.infrastructure import secure_queries


# Mapping fermé outil -> requête sécurisée. Les lambdas résolvent l'attribut du
# module au moment de l'appel (testabilité) tout en gardant un ensemble figé.
_TOOL_HANDLERS: dict[ToolName, Callable[[str, dict[str, Any]], dict[str, Any]]] = {
    ToolName.EMPLOYEE_COUNT: lambda cid, args: secure_queries.count_employees(cid, args),
    ToolName.EMPLOYEE_SEARCH: lambda cid, args: secure_queries.search_employees(cid, args),
    ToolName.PAYROLL_SUMMARY: lambda cid, args: secure_queries.payroll_summary(cid, args),
    ToolName.ABSENCE_SUMMARY: lambda cid, args: secure_queries.absence_summary(cid, args),
    ToolName.PLANNING_SUMMARY: lambda cid, args: secure_queries.planning_summary(cid, args),
    ToolName.HR_INDICATORS: lambda cid, args: secure_queries.hr_indicators(cid, args),
}


def execute_tool(call: ToolCall, company_id: str) -> dict[str, Any]:
    """Exécute un outil validé avec le company_id serveur imposé."""
    handler = _TOOL_HANDLERS[call.tool]
    return handler(company_id, call.arguments)
