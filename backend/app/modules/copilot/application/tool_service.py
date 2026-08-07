"""
Dispatch fermé des outils Copilot.

``execute_tool`` est la SEULE façon d'exécuter un outil validé. Le mapping est
explicite et exhaustif : aucun import dynamique, aucun ``getattr`` sur une
entrée LLM, aucune chaîne SQL / nom de table / requête issue du modèle.

Le ``company_id`` transmis à la requête sécurisée est TOUJOURS celui du serveur
(argument positionnel), jamais une valeur fournie par le LLM. Il en va de même
du ``user_id``, qui porte le périmètre des outils nominatifs.
"""

from __future__ import annotations

from typing import Any, Callable

from app.modules.copilot.domain.tools import OUTILS_NOMINATIFS, ToolCall, ToolName
from app.modules.copilot.infrastructure import secure_queries


# Mapping fermé outil -> requête sécurisée. Les lambdas résolvent l'attribut du
# module au moment de l'appel (testabilité) tout en gardant un ensemble figé.
# Signature uniforme ``(company_id, arguments, user_id)`` : les outils agrégés
# ignorent le ``user_id``, les outils nominatifs s'en servent pour borner le
# périmètre.
_TOOL_HANDLERS: dict[
    ToolName, Callable[[str, dict[str, Any], str, str], dict[str, Any]]
] = {
    ToolName.EMPLOYEE_COUNT: lambda cid, args, uid, role: secure_queries.count_employees(cid, args),
    ToolName.EMPLOYEE_SEARCH: lambda cid, args, uid, role: secure_queries.search_employees(cid, args),
    ToolName.PAYROLL_SUMMARY: lambda cid, args, uid, role: secure_queries.payroll_summary(cid, args),
    ToolName.ABSENCE_SUMMARY: lambda cid, args, uid, role: secure_queries.absence_summary(cid, args),
    ToolName.PLANNING_SUMMARY: lambda cid, args, uid, role: secure_queries.planning_summary(cid, args),
    ToolName.HR_INDICATORS: lambda cid, args, uid, role: secure_queries.hr_indicators(cid, args),
    ToolName.ABSENCES_EN_COURS: lambda cid, args, uid, role: secure_queries.absences_en_cours(
        cid, args, uid, role
    ),
    ToolName.ECHEANCES_RH: lambda cid, args, uid, role: secure_queries.echeances_rh(
        cid, args, uid, role
    ),
    ToolName.EMPLOYEE_DETAIL: lambda cid, args, uid, role: secure_queries.employee_detail(
        cid, args, uid, role
    ),
}


def execute_tool(
    call: ToolCall, company_id: str, user_id: str = "", user_role: str = ""
) -> dict[str, Any]:
    """Exécute un outil validé avec le company_id et le user_id serveur imposés.

    Un outil nominatif sans ``user_id`` exploitable ne s'exécute pas : sans
    utilisateur, il n'existe pas de périmètre, et retomber sur l'entreprise
    entière reviendrait à publier des données personnelles à qui n'y a pas
    droit. Les outils agrégés, eux, restent accessibles.
    """
    if call.tool in OUTILS_NOMINATIFS and not (user_id or "").strip():
        raise ValueError(
            f"L'outil {call.tool.value} exige un utilisateur pour évaluer son "
            "périmètre d'accès."
        )
    handler = _TOOL_HANDLERS[call.tool]
    return handler(company_id, call.arguments, user_id, user_role)
