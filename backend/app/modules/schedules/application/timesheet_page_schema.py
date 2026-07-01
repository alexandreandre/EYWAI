"""Schéma JSON et prompts pour extraction IA par page de relevé de pointages."""

from __future__ import annotations

from typing import Any

PAGE_DAY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "jour": {"type": "integer"},
        "weekday": {"type": ["string", "integer", "null"]},
        "debut": {"type": ["string", "null"]},
        "fin": {"type": ["string", "null"]},
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
        "week_number": {"type": ["integer", "null"]},
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


def build_page_system_prompt(
    *, year: int, month: int, channel: str, week_anchor_context: str = ""
) -> str:
    channel_label = "IMAGE" if channel == "vision" else "TEXTE OCR"
    anchor_block = f"\n{week_anchor_context}\n" if week_anchor_context else ""
    return (
        "Assistant RH : extrais les pointages d'UN SEUL relevé de pointeuse "
        f"(canal {channel_label}) pour la page fournie.\n"
        f"Période cible : mois {month}/{year}.\n"
        f"{anchor_block}\n"
        "Règles :\n"
        "- Extraire UNIQUEMENT les salariés visibles sur CETTE page.\n"
        "- raw_name : nom tel qu'affiché (souvent NOM Prénom).\n"
        "- matricule : numéro GTA si présent, sinon null.\n"
        "- days : jours du mois cible avec heures (null si absent), type travail|conge|ferie|absence.\n"
        "- Utiliser les dates JJ/MM visibles pour déterminer `jour` du mois. "
        "Si aucune date JJ/MM n'est visible et qu'un ancrage hebdomadaire est fourni "
        "ci-dessus, utiliser cet ancrage (jamais une hypothèse par défaut comme "
        "« la semaine commence le 1er du mois »).\n"
        "- weekly_total_pdf : total hebdo si affiché, sinon null.\n"
        "- page_period_hint : ex. « SEMAINE 22 » si visible.\n"
        "- confidence : 0 à 1 selon la lisibilité.\n"
        "- warnings : toujours [] (tableau vide). N'écris aucun commentaire, note "
        "interprétative ni alerte sur les congés/annotations du PDF.\n"
        "- Ne pas inventer de salariés ni de jours absents de la page.\n"
        "- Formats possibles : bloc vertical par salarié OU tableau horizontal (jours en colonnes).\n"
        "- Feuille manuscrite photo (prénoms en majuscules, colonnes DEBUT/FIN par jour) : "
        "calculer les heures travaillées (FIN − DEBUT, déduire ~1 h de pause si créneau matin/après-midi), "
        "matricule null, lire la semaine en en-tête (ex. S18).\n"
        "- Pour une feuille manuscrite DEBUT/FIN : lire ligne par ligne ; le prénom est en colonne gauche ; "
        "renseigner week_number depuis l'en-tête Sxx ; renseigner weekday, debut et fin ; "
        "ne jamais inventer de matricule ; ignorer ruban jaune, signatures, gribouillis et cellules illisibles.\n"
        "- Si une cellule manuscrite est illisible, mettre heures null et baisser confidence.\n"
        "- Si le relevé est un tableau paysage (Lundi|Mardi|… en colonnes), lire ligne par ligne.\n"
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
        "Extrais tous les blocs salariés visibles sur cette page. "
        "Si feuille manuscrite avec DEBUT/FIN, lis chaque ligne prénom par prénom, "
        "extrais Sxx comme week_number, n'invente aucun matricule et calcule les heures par jour."
    )


__all__ = [
    "PAGE_EXTRACTION_JSON_SCHEMA",
    "build_page_system_prompt",
    "build_page_user_prompt_text",
    "build_page_user_prompt_vision",
]
