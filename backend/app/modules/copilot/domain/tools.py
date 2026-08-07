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
    # Outils nominatifs : ils désignent des personnes. Chacun est borné par la
    # permission scopée correspondante (cf. OUTILS_NOMINATIFS), en plus du
    # company_id serveur — un RH restreint à une équipe ne voit que la sienne.
    ABSENCES_EN_COURS = "absences_en_cours"
    ECHEANCES_RH = "echeances_rh"
    EMPLOYEE_DETAIL = "employee_detail"


# Outils qui renvoient des personnes identifiables. Le périmètre n'est jamais
# déduit du rôle seul : il passe par les grants scopés de `access_control`, qui
# sont fail-closed (aucun grant → aucune donnée).
OUTILS_NOMINATIFS: frozenset[ToolName] = frozenset(
    {
        ToolName.ABSENCES_EN_COURS,
        ToolName.ECHEANCES_RH,
        ToolName.EMPLOYEE_DETAIL,
    }
)


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


_ARGUMENT_TYPES: dict[ToolName, dict[str, type]] = {
    ToolName.EMPLOYEE_COUNT: {
        "employment_status": str,
        "contract_type": str,
    },
    ToolName.EMPLOYEE_SEARCH: {
        "name": str,
        "employment_status": str,
        "contract_type": str,
        "limit": int,
    },
    ToolName.PAYROLL_SUMMARY: {"period": str},
    ToolName.ABSENCE_SUMMARY: {
        "status": str,
        "type": str,
        "date_start": str,
        "date_end": str,
    },
    ToolName.PLANNING_SUMMARY: {"date_start": str, "date_end": str},
    ToolName.HR_INDICATORS: {},
    ToolName.ABSENCES_EN_COURS: {
        "date_start": str,
        "date_end": str,
        "type": str,
    },
    ToolName.ECHEANCES_RH: {"type": str, "jours": int},
    ToolName.EMPLOYEE_DETAIL: {"name": str},
}

# Types d'échéance connus. Le LLM ne peut pas en inventer un : une valeur hors
# liste est refusée au parsing plutôt que de produire un résultat vide qui
# passerait pour « aucune échéance ».
TYPES_ECHEANCE: frozenset[str] = frozenset(
    {"titre_sejour", "visite_medicale", "periode_essai", "fin_contrat"}
)


def _validate_arguments(tool: ToolName, arguments: dict[str, Any]) -> None:
    """Valide les clés et types autorisés pour un outil précis."""
    forbidden = FORBIDDEN_ARGUMENT_KEYS.intersection(arguments)
    if forbidden:
        raise ValueError(
            "Arguments interdits fournis par le LLM : "
            f"{', '.join(sorted(forbidden))}."
        )

    schema = _ARGUMENT_TYPES[tool]
    unknown = set(arguments).difference(schema)
    if unknown:
        raise ValueError(
            f"Argument non autorisé pour {tool.value} : "
            f"{', '.join(sorted(unknown))}."
        )

    for key, value in arguments.items():
        expected = schema[key]
        # ``bool`` est un sous-type de ``int`` en Python : on le refuse
        # explicitement pour éviter qu'un booléen soit accepté comme limite.
        if type(value) is not expected:
            raise ValueError(
                f"Type invalide pour l'argument {key} de {tool.value}."
            )

    if tool is ToolName.ECHEANCES_RH:
        demande = arguments.get("type")
        if demande is not None and demande not in TYPES_ECHEANCE:
            raise ValueError(
                f"Type d'échéance inconnu : {demande!r}. "
                f"Attendu : {', '.join(sorted(TYPES_ECHEANCE))}."
            )


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
        unknown_call_keys = set(item).difference({"tool", "arguments"})
        if unknown_call_keys:
            raise ValueError("Clé non autorisée dans un appel d'outil.")

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

        _validate_arguments(tool, arguments)

        calls.append(ToolCall(tool=tool, arguments=dict(arguments)))

    return calls
