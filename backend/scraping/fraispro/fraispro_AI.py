#!/usr/bin/env python3
"""Source IA — frais professionnels URSSAF (Sonar par section, tableaux injectés)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

_SCRAPING = Path(__file__).resolve().parent.parent
_DIR = Path(__file__).resolve().parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from core.ai_extractor import (  # noqa: E402
    build_standard_payload,
    emit_ai_payload_or_exit,
    extract_structured_json,
    last_citation,
)
from core.year_utils import current_year  # noqa: E402

from _logic import (  # noqa: E402
    _eq_metropole,
    _eq_mobilite,
    _eq_mutation,
    _eq_outre_mer,
    _eq_petit_dep,
    _eq_repas,
    _eq_teletravail,
    _norm_metropole,
    _norm_mobilite,
    _norm_mutation,
    _norm_outre_mer,
    _norm_petit_dep,
    _norm_repas,
    _norm_teletravail,
)

_FRAISPRO_FILE = Path(__file__).resolve().parent / "fraispro.py"
_spec = importlib.util.spec_from_file_location("fraispro_primary", _FRAISPRO_FILE)
assert _spec and _spec.loader
fraispro_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fraispro_module)

URL = fraispro_module.URL_URSSAF

PETIT_DEP_ITEM = {
    "type": "object",
    "properties": {
        "km_min": {"type": "number"},
        "km_max": {"type": "number"},
        "montant": {"type": "number"},
    },
    "required": ["km_min", "km_max", "montant"],
    "additionalProperties": False,
}

METROPOLE_ITEM = {
    "type": "object",
    "properties": {
        "periode_sejour": {"type": "string"},
        "repas": {"type": "number"},
        "logement_paris_banlieue": {"type": "number"},
        "logement_province": {"type": "number"},
    },
    "required": [
        "periode_sejour",
        "repas",
        "logement_paris_banlieue",
        "logement_province",
    ],
    "additionalProperties": False,
}

OUTRE_MER_ITEM = {
    "type": "object",
    "properties": {
        "periode_sejour": {"type": "string"},
        "hebergement": {"type": "number"},
        "repas": {"type": "number"},
    },
    "required": ["periode_sejour", "hebergement", "repas"],
    "additionalProperties": False,
}

METROPOLE_ONLY_SCHEMA = {
    "type": "object",
    "properties": {"metropole": {"type": "array", "items": METROPOLE_ITEM}},
    "required": ["metropole"],
    "additionalProperties": False,
}

OM_G1_SCHEMA = {
    "type": "object",
    "properties": {
        "outre_mer_groupe1": {"type": "array", "items": OUTRE_MER_ITEM},
    },
    "required": ["outre_mer_groupe1"],
    "additionalProperties": False,
}

OM_G2_SCHEMA = {
    "type": "object",
    "properties": {
        "outre_mer_groupe2": {"type": "array", "items": OUTRE_MER_ITEM},
    },
    "required": ["outre_mer_groupe2"],
    "additionalProperties": False,
}

SECTION_CONFIG: tuple[tuple[str, str, dict, Callable], ...] = (
    (
        "repas",
        "ancre-repas",
        {
            "type": "object",
            "properties": {
                "sur_lieu_travail": {"type": "number"},
                "hors_locaux_sans_restaurant": {"type": "number"},
                "hors_locaux_avec_restaurant": {"type": "number"},
            },
            "required": [
                "sur_lieu_travail",
                "hors_locaux_sans_restaurant",
                "hors_locaux_avec_restaurant",
            ],
            "additionalProperties": False,
        },
        lambda d: d,
    ),
    (
        "petit_deplacement",
        "ancre-petit-deplacement",
        {
            "type": "object",
            "properties": {
                "petit_deplacement": {
                    "type": "array",
                    "items": PETIT_DEP_ITEM,
                }
            },
            "required": ["petit_deplacement"],
            "additionalProperties": False,
        },
        lambda d: d["petit_deplacement"],
    ),
    (
        "mutation_professionnelle",
        "ancre-mutation-professionnelle",
        {
            "type": "object",
            "properties": {
                "hebergement_provisoire": {
                    "type": "object",
                    "properties": {"montant_par_jour": {"type": "number"}},
                    "required": ["montant_par_jour"],
                    "additionalProperties": False,
                },
                "hebergement_definitif": {
                    "type": "object",
                    "properties": {
                        "frais_installation": {"type": "number"},
                        "majoration_par_enfant": {"type": "number"},
                        "plafond_total": {"type": "number"},
                    },
                    "required": [
                        "frais_installation",
                        "majoration_par_enfant",
                        "plafond_total",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": ["hebergement_provisoire", "hebergement_definitif"],
            "additionalProperties": False,
        },
        lambda d: d,
    ),
    (
        "mobilite_durable",
        "ancre-forfait-mobilites-durables",
        {
            "type": "object",
            "properties": {
                "employeurs_prives": {
                    "type": "object",
                    "properties": {
                        "limite_base": {"type": "number"},
                        "limite_cumul_transport_public": {"type": "number"},
                        "limite_cumul_carburant_total": {"type": "number"},
                        "limite_cumul_carburant_part_carburant": {"type": "number"},
                    },
                    "required": [
                        "limite_base",
                        "limite_cumul_transport_public",
                        "limite_cumul_carburant_total",
                        "limite_cumul_carburant_part_carburant",
                    ],
                    "additionalProperties": False,
                },
                "employeurs_publics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "jours_utilises": {"type": "string"},
                            "montant_annuel": {"type": "number"},
                        },
                        "required": ["jours_utilises", "montant_annuel"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["employeurs_prives", "employeurs_publics"],
            "additionalProperties": False,
        },
        lambda d: d,
    ),
    (
        "teletravail",
        "ancre-teletravail-utilisation-de-mater",
        {
            "type": "object",
            "properties": {
                "indemnite_sans_accord": {
                    "type": "object",
                    "properties": {
                        "par_jour": {"type": "number"},
                        "limite_mensuelle": {"type": "number"},
                        "par_mois_pour_1_jour_semaine": {"type": "number"},
                    },
                    "required": [
                        "par_jour",
                        "limite_mensuelle",
                        "par_mois_pour_1_jour_semaine",
                    ],
                    "additionalProperties": False,
                },
                "indemnite_avec_accord": {
                    "type": "object",
                    "properties": {
                        "par_jour": {"type": "number"},
                        "limite_mensuelle": {"type": "number"},
                        "par_mois_pour_1_jour_semaine": {"type": "number"},
                    },
                    "required": [
                        "par_jour",
                        "limite_mensuelle",
                        "par_mois_pour_1_jour_semaine",
                    ],
                    "additionalProperties": False,
                },
                "materiel_informatique_perso": {
                    "type": "object",
                    "properties": {"montant_mensuel": {"type": "number"}},
                    "required": ["montant_mensuel"],
                    "additionalProperties": False,
                },
            },
            "required": [
                "indemnite_sans_accord",
                "indemnite_avec_accord",
                "materiel_informatique_perso",
            ],
            "additionalProperties": False,
        },
        lambda d: d,
    ),
)

_SECTION_MATCHERS: dict[str, Callable[[Any, Any], bool]] = {
    "repas": _eq_repas,
    "petit_deplacement": _eq_petit_dep,
    "grand_deplacement": lambda a, b: (
        _eq_metropole(a.get("metropole", []), b.get("metropole", []))
        and _eq_outre_mer(
            a.get("outre_mer_groupe1", []), b.get("outre_mer_groupe1", [])
        )
        and _eq_outre_mer(
            a.get("outre_mer_groupe2", []), b.get("outre_mer_groupe2", [])
        )
    ),
    "mutation_professionnelle": _eq_mutation,
    "mobilite_durable": _eq_mobilite,
    "teletravail": _eq_teletravail,
}


def _normalize_section(section_key: str, value: Any) -> Any:
    if section_key == "repas":
        return _norm_repas(value)
    if section_key == "petit_deplacement":
        return _norm_petit_dep(value)
    if section_key == "grand_deplacement":
        gd = value or {}
        return {
            "metropole": _norm_metropole(gd.get("metropole")),
            "outre_mer_groupe1": _norm_outre_mer(gd.get("outre_mer_groupe1")),
            "outre_mer_groupe2": _norm_outre_mer(gd.get("outre_mer_groupe2")),
        }
    if section_key == "mutation_professionnelle":
        return _norm_mutation(value)
    if section_key == "mobilite_durable":
        return _norm_mobilite(value)
    if section_key == "teletravail":
        return _norm_teletravail(value)
    return value


def _section_prompt(section_key: str, table_text: str) -> str:
    return (
        f"Section URSSAF « {section_key} » — barèmes frais professionnels "
        f"applicables en {current_year()}.\n"
        f"Extrais EXACTEMENT les montants du tableau ci-dessous (en euros).\n\n"
        f"--- TABLEAU OFFICIEL ---\n{table_text}\n--- FIN TABLEAU ---\n\n"
        f"Recopie les chiffres tels quels, sans inventer de valeurs."
    )


def _align_periode_labels(
    rows: list[dict],
    ref_rows: list[dict],
    *,
    sort_key: Callable[[dict], tuple],
) -> list[dict]:
    """Recopie les libellés URSSAF du parse primary (ordre numérique)."""
    paired = zip(sorted(rows, key=sort_key), sorted(ref_rows, key=sort_key))
    return [
        {**row, "periode_sejour": ref["periode_sejour"]}
        for row, ref in paired
    ]


def _metro_sort(row: dict) -> tuple:
    return (
        -float(row.get("repas") or 0),
        -float(row.get("logement_paris_banlieue") or 0),
        -float(row.get("logement_province") or 0),
    )


def _om_sort(row: dict) -> tuple:
    return (-float(row.get("repas") or 0), -float(row.get("hebergement") or 0))


def _extract_sonar_block(
    *,
    section_key: str,
    schema_name: str,
    schema: dict,
    table_text: str,
    post_process: Callable[[dict], Any],
    reference_value: Any,
    matcher: Callable[[Any, Any], bool],
    citation_date: str,
    max_attempts: int = 3,
) -> Any | None:
    for attempt in range(1, max_attempts + 1):
        retry = f"\n(Tentative {attempt}/{max_attempts}.)" if attempt > 1 else ""
        data = extract_structured_json(
            task_prompt=_section_prompt(section_key, table_text) + retry,
            json_schema=schema,
            schema_name=schema_name,
            citation_url=URL,
            citation_date=citation_date,
            use_web_search=False,
        )
        if not data:
            continue
        try:
            parsed = post_process(data)
        except (KeyError, TypeError):
            continue
        ref_norm = reference_value
        got_norm = parsed
        if matcher(got_norm, ref_norm):
            return parsed
        print(
            f"[fraispro_AI] Bloc {schema_name} : écart vs parse URSSAF.",
            file=sys.stderr,
        )
    return None


def extract_grand_deplacement(soup, reference: dict, citation_date: str) -> dict | None:
    ref_gd = reference["grand_deplacement"]
    metro = _extract_sonar_block(
        section_key="grand_deplacement métropole",
        schema_name="fraispro_grand_deplacement_metropole",
        schema=METROPOLE_ONLY_SCHEMA,
        table_text=fraispro_module.subsection_text(
            soup, r"Déplacements en métropole", r"Déplacement en Outre-mer"
        ),
        post_process=lambda d: d["metropole"],
        reference_value=ref_gd["metropole"],
        matcher=_eq_metropole,
        citation_date=citation_date,
    )
    if metro is None:
        return None

    om1 = _extract_sonar_block(
        section_key="grand_deplacement outre-mer groupe 1",
        schema_name="fraispro_grand_deplacement_om1",
        schema=OM_G1_SCHEMA,
        table_text=fraispro_module.subsection_text(
            soup, r"Martinique, Guadeloupe", r"Nouvelle-Calédonie"
        ),
        post_process=lambda d: d["outre_mer_groupe1"],
        reference_value=ref_gd["outre_mer_groupe1"],
        matcher=_eq_outre_mer,
        citation_date=citation_date,
    )
    if om1 is None:
        return None

    om2 = _extract_sonar_block(
        section_key="grand_deplacement outre-mer groupe 2",
        schema_name="fraispro_grand_deplacement_om2",
        schema=OM_G2_SCHEMA,
        table_text=fraispro_module.subsection_text(
            soup, r"Nouvelle-Calédonie", None
        ),
        post_process=lambda d: d["outre_mer_groupe2"],
        reference_value=ref_gd["outre_mer_groupe2"],
        matcher=_eq_outre_mer,
        citation_date=citation_date,
    )
    if om2 is None:
        return None

    return {
        "metropole": _align_periode_labels(
            metro, ref_gd["metropole"], sort_key=_metro_sort
        ),
        "outre_mer_groupe1": _align_periode_labels(
            om1, ref_gd["outre_mer_groupe1"], sort_key=_om_sort
        ),
        "outre_mer_groupe2": _align_periode_labels(
            om2, ref_gd["outre_mer_groupe2"], sort_key=_om_sort
        ),
    }


def extract_section(
    section_key: str,
    anchor_id: str,
    schema: dict,
    post_process: Callable,
    *,
    soup,
    reference: dict,
    citation_date: str,
    max_attempts: int = 3,
) -> Any | None:
    table_text = fraispro_module.section_text(soup, anchor_id)
    ref_value = reference.get(section_key)
    matcher = _SECTION_MATCHERS[section_key]

    for attempt in range(1, max_attempts + 1):
        retry = f"\n(Tentative {attempt}/{max_attempts}.)" if attempt > 1 else ""
        data = extract_structured_json(
            task_prompt=_section_prompt(section_key, table_text) + retry,
            json_schema=schema,
            schema_name=f"fraispro_{section_key}",
            citation_url=URL,
            citation_date=citation_date,
            use_web_search=False,
        )
        if not data:
            continue
        try:
            parsed = post_process(data)
        except (KeyError, TypeError):
            continue
        if matcher(
            _normalize_section(section_key, parsed),
            _normalize_section(section_key, ref_value),
        ):
            return parsed
        print(
            f"[fraispro_AI] Section {section_key} : écart vs parse URSSAF.",
            file=sys.stderr,
        )
    return None


def build_sections() -> dict | None:
    citation_date = f"01/01/{current_year()}"
    soup = fraispro_module.fetch_soup(URL)
    reference = fraispro_module.scrape_all_sections(soup)
    sections: dict = {}

    for section_key, anchor_id, schema, post_process in SECTION_CONFIG:
        value = extract_section(
            section_key,
            anchor_id,
            schema,
            post_process,
            soup=soup,
            reference=reference,
            citation_date=citation_date,
        )
        if value is None:
            return None
        sections[section_key] = value

    grand = extract_grand_deplacement(soup, reference, citation_date)
    if grand is None:
        return None
    sections["grand_deplacement"] = grand

    return sections


def main() -> None:
    print(f"[fraispro_AI] URL URSSAF : {URL}", file=sys.stderr)
    sections = build_sections()
    if not sections:
        print(
            "ERREUR CRITIQUE: extraction IA frais pro échouée (Sonar par section).",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = build_standard_payload(
        item_id="frais_pro",
        item_type="frais_professionnels",
        libelle="Frais professionnels (IA)",
        sections_or_valeurs=sections,
        generator="fraispro/fraispro_AI.py",
        source_url=URL,
        source_label="URSSAF frais professionnels (Sonar par section, tableaux officiels)",
        citation_url=last_citation().get("url") or URL,
        citation_date=last_citation().get("date") or f"01/01/{current_year()}",
    )
    emit_ai_payload_or_exit(payload, "frais_pro")


if __name__ == "__main__":
    main()
