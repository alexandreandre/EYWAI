"""Schéma JSON et prompts pour extraction IA par page de relevé de pointages."""

from __future__ import annotations

from typing import Any

PAGE_DAY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "jour": {"type": "integer"},
        "heures": {"type": ["number", "null"]},
        "type": {"type": "string"},
    },
    "required": ["jour", "heures", "type"],
}

PAGE_EMPLOYEE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "raw_name": {"type": "string"},
        "matricule": {"type": ["string", "null"]},
        "weekly_total_pdf": {"type": ["number", "null"]},
        "days": {
            "type": "array",
            "items": PAGE_DAY_SCHEMA,
        },
    },
    "required": ["raw_name", "matricule", "weekly_total_pdf", "days"],
}

PAGE_EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "employees": {
            "type": "array",
            "items": PAGE_EMPLOYEE_SCHEMA,
        },
        "page_period_hint": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["employees", "page_period_hint", "confidence", "warnings"],
}


def build_page_system_prompt(*, year: int, month: int, channel: str) -> str:
    channel_label = "IMAGE" if channel == "vision" else "TEXTE OCR"
    return (
        "Assistant RH : extrais les pointages d'UN SEUL relevé de pointeuse "
        f"(canal {channel_label}) pour la page fournie.\n"
        f"Période cible : mois {month}/{year}.\n\n"
        "Règles :\n"
        "- Extraire UNIQUEMENT les salariés visibles sur CETTE page.\n"
        "- raw_name : nom tel qu'affiché (souvent NOM Prénom).\n"
        "- matricule : numéro GTA si présent, sinon null.\n"
        "- days : jours du mois cible avec heures (null si absent), type travail|conge|ferie|absence.\n"
        "- Utiliser les dates JJ/MM visibles pour déterminer `jour` du mois.\n"
        "- weekly_total_pdf : total hebdo si affiché, sinon null.\n"
        "- page_period_hint : ex. « SEMAINE 22 » si visible.\n"
        "- confidence : 0 à 1 selon la lisibilité.\n"
        "- warnings : toujours [] (tableau vide). N'écris aucun commentaire, note "
        "interprétative ni alerte sur les congés/annotations du PDF.\n"
        "- Ne pas inventer de salariés ni de jours absents de la page.\n"
        "- Ignorer pieds de page (« Édition en heures et minutes », totaux globaux sans salarié).\n"
    )


def build_page_user_prompt_text(
    *,
    ocr_text: str,
    page_index: int,
    pages_total: int,
    matricule_hint: str = "",
) -> str:
    return (
        f"Page {page_index}/{pages_total} du relevé.\n"
        f"{matricule_hint}\n"
        "--- OCR PAGE ---\n"
        f"{ocr_text or '(vide)'}"
    )


def build_page_user_prompt_vision(
    *,
    page_index: int,
    pages_total: int,
    matricule_hint: str = "",
) -> str:
    return (
        f"Page {page_index}/{pages_total} du relevé scanné ci-joint.\n"
        f"{matricule_hint}\n"
        "Extrais tous les blocs salariés visibles sur cette page."
    )


__all__ = [
    "PAGE_EXTRACTION_JSON_SCHEMA",
    "build_page_system_prompt",
    "build_page_user_prompt_text",
    "build_page_user_prompt_vision",
]
