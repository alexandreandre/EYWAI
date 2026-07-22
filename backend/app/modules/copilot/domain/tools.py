"""
Catalogue fermé d'outils Copilot et parsing strict des appels d'outils LLM.

Ce module définit :
- ``ToolName`` : l'ensemble EXHAUSTIF des outils autorisés (aucun autre n'est
  exécutable) ;
- ``ToolCall`` : un appel d'outil validé (nom typé + arguments) ;
- ``parse_tool_calls`` : la seule porte d'entrée pour transformer une sortie LLM
  brute en appels exécutables.

Garanties de sécurité (fail-closed) :
- le LLM ne peut PAS choisir un outil hors du catalogue ;
- le LLM ne peut PAS fournir de ``company_id``, d'identifiant de groupe,
  d'identifiants internes de périmètre (``employee_ids``), ni de SQL / table /
  requête brute ;
- au plus cinq appels par tour ;
- des arguments qui ne sont pas un dictionnaire sont refusés.

Aucun accès base ni réseau : logique purement domaine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ToolName(StrEnum):
    """Ensemble fermé des outils RH exposés au LLM."""

    EMPLOYEE_COUNT = "employee_count"
    EMPLOYEE_SEARCH = "employee_search"
    PAYROLL_SUMMARY = "payroll_summary"
    ABSENCE_SUMMARY = "absence_summary"
    PLANNING_SUMMARY = "planning_summary"
    HR_INDICATORS = "hr_indicators"


@dataclass(frozen=True)
class ToolCall:
    """Appel d'outil validé et prêt à être exécuté avec le company_id serveur."""

    tool: ToolName
    arguments: dict[str, Any] = field(default_factory=dict)


# Clés d'arguments STRICTEMENT interdites en provenance du LLM : elles
# permettraient de contourner le scoping serveur (entreprise/groupe) ou
# d'injecter du SQL / des identifiants internes de périmètre.
FORBIDDEN_ARGUMENT_KEYS: frozenset[str] = frozenset(
    {
        "company_id",
        "group_id",
        "sql",
        "query",
        "table",
        "employee_ids",
    }
)

# Nombre maximal d'appels d'outils autorisés par tour.
MAX_TOOL_CALLS = 5


def parse_tool_calls(raw: Any) -> list[ToolCall]:
    """Valide et convertit la sortie LLM brute en liste d'``ToolCall``.

    Lève ``ValueError`` dès qu'une contrainte de sécurité est violée. Une
    entrée vide (``None`` ou liste vide) renvoie une liste vide (aucun outil).
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("Les appels d'outils doivent être fournis sous forme de liste.")
    if len(raw) > MAX_TOOL_CALLS:
        raise ValueError(
            f"Trop d'appels d'outils ({len(raw)} > {MAX_TOOL_CALLS})."
        )

    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Chaque appel d'outil doit être un objet.")

        raw_name = item.get("tool")
        try:
            tool = ToolName(raw_name)
        except ValueError as exc:
            raise ValueError(f"Outil inconnu ou non autorisé : {raw_name!r}.") from exc

        arguments = item.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ValueError("Les arguments d'un outil doivent être un objet.")

        forbidden = FORBIDDEN_ARGUMENT_KEYS.intersection(arguments.keys())
        if forbidden:
            raise ValueError(
                "Arguments interdits fournis par le LLM : "
                f"{', '.join(sorted(forbidden))}."
            )

        calls.append(ToolCall(tool=tool, arguments=dict(arguments)))

    return calls
