"""L'appel à Claude. Le SDK n'est importé qu'au moment de créer le vrai client."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from app.modules.relecture_ia.domain.garde import GRAVITES

logger = logging.getLogger(__name__)

MODELE = "claude-opus-5-5"
_BETA_REPLI = "server-side-fallback-2026-07-01"
_MAX_TOKENS = 16_000
_MAX_TOKENS_ELARGI = 32_000
_DELAI_SECONDES = 300.0
_NOUVEAUX_ESSAIS = 3

_MESSAGE_SANS_CLE = (
    "La relecture n'est pas encore branchée : la clé d'accès à l'IA n'est pas posée sur le "
    "serveur. Demandez à l'équipe Martine de la poser."
)
_MESSAGE_CLE_REFUSEE = (
    "L'IA refuse la clé d'accès de Martine. La relecture est arrêtée : demandez à l'équipe "
    "Martine de vérifier la clé."
)
_MESSAGE_SANS_SDK = (
    "La relecture n'est pas disponible sur ce serveur : un composant manque. Demandez à "
    "l'équipe Martine de le redéployer."
)
_MESSAGE_REFUS = "L'IA a refusé de relire ce bulletin. Regardez-le vous-même."
_MESSAGE_TROP_LONG = "Ce bulletin est trop long pour l'IA. Regardez-le vous-même."
_MESSAGE_ILLISIBLE = (
    "La réponse de l'IA pour ce bulletin était illisible. Relancez la relecture pour le reprendre."
)
_MESSAGE_PAS_DE_REPONSE = (
    "L'IA n'a pas répondu pour ce bulletin. Relancez la relecture pour le reprendre."
)

SCHEMA_REPONSE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "signalements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gravite": {"type": "string", "enum": list(GRAVITES)},
                    "ligne": {"type": "string"},
                    "raison": {"type": "string"},
                    "chiffres_cites": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["gravite", "ligne", "raison", "chiffres_cites"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["signalements"],
    "additionalProperties": False,
}

_CHAMPS_USAGE = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


class RelectureImpossible(Exception):
    """Un blocage à dire tel quel. `fatale` : inutile de continuer sur les autres bulletins."""

    def __init__(self, message: str, *, fatale: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.fatale = fatale


@dataclass
class ReponseRelecture:
    signalements: list[dict[str, Any]]
    usage: dict[str, int] = field(default_factory=dict)


def cle_presente() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def creer_client() -> Any:
    """Le vrai client. `import anthropic` reste ici : le module se charge sans le SDK."""
    cle = os.environ.get("ANTHROPIC_API_KEY")
    if not cle:
        raise RelectureImpossible(_MESSAGE_SANS_CLE, fatale=True)
    try:
        import anthropic
    except ImportError as exc:
        raise RelectureImpossible(_MESSAGE_SANS_SDK, fatale=True) from exc
    options: dict[str, Any] = {
        "api_key": cle,
        "timeout": _DELAI_SECONDES,
        "max_retries": _NOUVEAUX_ESSAIS,
    }
    espace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if espace:
        options["default_headers"] = {"anthropic-workspace-id": espace}
    return anthropic.Anthropic(**options)


def _usage_de(reponse: Any) -> dict[str, int]:
    usage = getattr(reponse, "usage", None)
    return {champ: int(getattr(usage, champ, 0) or 0) for champ in _CHAMPS_USAGE}


def _cumuler(total: dict[str, int], ajout: dict[str, int]) -> dict[str, int]:
    return {champ: total.get(champ, 0) + ajout.get(champ, 0) for champ in _CHAMPS_USAGE}


class RelecteurClaude:
    """`client` injectable pour les tests ; sinon créé au premier appel."""

    def __init__(self, client: Any = None) -> None:
        self._client = client

    def _obtenir_client(self) -> Any:
        if self._client is None:
            self._client = creer_client()
        return self._client

    def _appeler(
        self, systeme: list[dict[str, Any]], fiche: dict[str, Any], max_tokens: int
    ) -> Any:
        contenu = json.dumps(fiche, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        try:
            return self._obtenir_client().beta.messages.create(
                model=MODELE,
                max_tokens=max_tokens,
                betas=[_BETA_REPLI],
                fallbacks="default",
                system=systeme,
                messages=[
                    {
                        "role": "user",
                        "content": f"Voici la fiche du bulletin à relire :\n{contenu}",
                    }
                ],
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": SCHEMA_REPONSE},
                },
            )
        except RelectureImpossible:
            raise
        except Exception as exc:
            statut = getattr(exc, "status_code", None)
            logger.warning("Relecture IA : appel échoué (%s, statut=%s)", type(exc).__name__, statut)
            if statut in (401, 403):
                raise RelectureImpossible(_MESSAGE_CLE_REFUSEE, fatale=True) from exc
            raise RelectureImpossible(_MESSAGE_PAS_DE_REPONSE) from exc

    def relire(
        self, systeme: list[dict[str, Any]], fiche: dict[str, Any]
    ) -> ReponseRelecture:
        reponse = self._appeler(systeme, fiche, _MAX_TOKENS)
        usage = _usage_de(reponse)
        if reponse.stop_reason == "max_tokens":
            reponse = self._appeler(systeme, fiche, _MAX_TOKENS_ELARGI)
            usage = _cumuler(usage, _usage_de(reponse))
            if reponse.stop_reason == "max_tokens":
                raise RelectureImpossible(_MESSAGE_TROP_LONG)
        if reponse.stop_reason == "refusal":
            raise RelectureImpossible(_MESSAGE_REFUS)

        texte = next((b.text for b in reponse.content if b.type == "text"), "")
        try:
            signalements = json.loads(texte)["signalements"]
        except (ValueError, KeyError, TypeError) as exc:
            raise RelectureImpossible(_MESSAGE_ILLISIBLE) from exc
        if not isinstance(signalements, list):
            raise RelectureImpossible(_MESSAGE_ILLISIBLE)
        return ReponseRelecture(signalements=signalements, usage=usage)
