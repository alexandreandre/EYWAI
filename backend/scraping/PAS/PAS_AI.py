#!/usr/bin/env python3
"""Source IA PAS — Sonar par zone (3 appels) sur le tableau BOFIP officiel.

La recherche web seule mélange les grilles DOM-TOM ; on télécharge le BOFIP,
on isole le texte de chaque tableau, puis Sonar structure les 20 tranches
de cette zone uniquement (sans confondre métropole / GRM / Guyane).
"""

from __future__ import annotations

import importlib.util
import math
import re
import sys
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core import ai_extractor as ai_extractor_mod  # noqa: E402
from core.ai_extractor import (  # noqa: E402
    build_standard_payload,
    emit_ai_payload_or_exit,
    extract_structured_json,
    last_citation,
)
from core.year_utils import current_year  # noqa: E402

_PAS_FILE = Path(__file__).resolve().parent / "PAS.py"
_spec = importlib.util.spec_from_file_location("pas_bofip_primary", _PAS_FILE)
assert _spec and _spec.loader
pas_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pas_module)

NB_TRANCHES = 20

ZONES: tuple[tuple[str, str], ...] = (
    ("metropole", "métropole et hors de France"),
    ("guadeloupe_reunion_martinique", "Guadeloupe, Réunion et Martinique"),
    ("guyane_mayotte", "Guyane et Mayotte"),
)


def _date_from_bofip_url(url: str) -> str:
    m = re.search(r"BOI-BAREME-000037-(\d{8})", url)
    if not m:
        return f"01/01/{current_year()}"
    d = m.group(1)
    return f"{d[6:8]}/{d[4:6]}/{d[0:4]}"


def _zone_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "tranches": {
                "type": "array",
                "description": f"Exactement {NB_TRANCHES} tranches du barème mensuel",
                "items": {
                    "type": "object",
                    "properties": {
                        "plafond": {
                            "type": ["number", "null"],
                            "description": (
                                "Borne supérieure en euros "
                                "(null pour la dernière tranche)"
                            ),
                        },
                        "taux_pct": {
                            "type": "number",
                            "description": "Taux en % brut (ex: 0.5 pour 0,5 %)",
                        },
                    },
                    "required": ["plafond", "taux_pct"],
                    "additionalProperties": False,
                },
                "minItems": NB_TRANCHES,
                "maxItems": NB_TRANCHES,
            },
        },
        "required": ["tranches"],
        "additionalProperties": False,
    }


def _to_rate_pct(v: object) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", ".").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    if x < 0:
        return None
    if 0 < x < 0.02:
        return round(x, 5)
    return round(x / 100.0, 5)


def normalize_tranches(raw: list) -> list[dict] | None:
    if not isinstance(raw, list) or len(raw) != NB_TRANCHES:
        return None
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            return None
        taux = _to_rate_pct(item.get("taux_pct", item.get("taux")))
        if taux is None:
            return None
        plafond = item.get("plafond")
        if plafond is not None:
            try:
                plafond = round(float(plafond), 2)
            except (TypeError, ValueError):
                return None
        out.append({"plafond": plafond, "taux": taux})
    out.sort(key=lambda x: float("inf") if x["plafond"] is None else x["plafond"])
    if out[-1]["plafond"] is not None:
        return None
    return out


def tranches_match_reference(
    got: list[dict],
    ref: list[dict],
    *,
    plafond_tol: float = 1e-6,
    taux_tol: float = 1e-6,
) -> bool:
    if len(got) != len(ref):
        return False
    for a, b in zip(got, ref):
        pa, pb = a.get("plafond"), b.get("plafond")
        if pa is None and pb is None:
            pass
        elif pa is None or pb is None:
            return False
        elif not math.isclose(float(pa), float(pb), abs_tol=plafond_tol):
            return False
        if not math.isclose(float(a["taux"]), float(b["taux"]), abs_tol=taux_tol):
            return False
    return True


def extract_zone_tranches(
    zone_key: str,
    zone_label: str,
    *,
    bofip_url: str,
    table_text: str,
    reference_tranches: list[dict],
    citation_date: str,
    max_attempts: int = 3,
) -> list[dict] | None:
    schema = _zone_schema()
    for attempt in range(1, max_attempts + 1):
        retry = f"\n(Tentative {attempt}/{max_attempts}.)" if attempt > 1 else ""
        data = extract_structured_json(
            task_prompt=(
                f"Zone géographique : {zone_label} ({zone_key}).\n"
                f"Document : BOFiP BOI-BAREME-000037 — barème mensuel du taux "
                f"neutre du prélèvement à la source.\n"
                f"Extrais EXACTEMENT les {NB_TRANCHES} tranches du tableau ci-dessous "
                f"(ne pas utiliser une autre zone).\n\n"
                f"--- TABLEAU OFFICIEL ---\n{table_text}\n--- FIN TABLEAU ---\n\n"
                f"Pour chaque tranche : plafond (euros, null si dernière ligne "
                f"« supérieure ou égale à »), taux_pct (ex: 0.5 pour 0,5 %). "
                f"Recopie les montants tels quels.{retry}"
            ),
            json_schema=schema,
            schema_name=f"pas_{zone_key}",
            citation_url=bofip_url,
            citation_date=citation_date,
            use_web_search=False,
        )
        if not data:
            continue
        tranches = normalize_tranches(data.get("tranches"))
        if tranches and tranches_match_reference(tranches, reference_tranches):
            return tranches
        print(
            f"[PAS_AI] Zone {zone_key} : écart vs tableau BOFIP ou format invalide.",
            file=sys.stderr,
        )
    return None


def build_sections(bofip_url: str | None = None) -> dict[str, list[dict]] | None:
    url = bofip_url or pas_module.get_latest_bofip_url()
    citation_date = _date_from_bofip_url(url)
    soup = pas_module.fetch_bofip_soup(url)
    reference = pas_module._parse_zones_from_soup(soup)
    sections: dict[str, list[dict]] = {}

    for zone_key, zone_label in ZONES:
        table_text = pas_module.zone_table_text(soup, zone_key)
        tranches = extract_zone_tranches(
            zone_key,
            zone_label,
            bofip_url=url,
            table_text=table_text,
            reference_tranches=reference[zone_key],
            citation_date=citation_date,
        )
        if not tranches:
            return None
        sections[zone_key] = tranches

    ai_extractor_mod._LAST_CITATION = {"url": url, "date": citation_date}
    return sections


def main() -> None:
    url = pas_module.get_latest_bofip_url()
    print(f"[PAS_AI] URL BOFIP prioritaire : {url}", file=sys.stderr)
    sections = build_sections(url)
    if not sections:
        print(
            "ERREUR CRITIQUE: extraction IA PAS échouée (Sonar par zone + BOFIP).",
            file=sys.stderr,
        )
        sys.exit(1)

    cited_url = last_citation().get("url") or url
    cited_date = last_citation().get("date") or _date_from_bofip_url(url)
    payload = build_standard_payload(
        item_id="pas_taux_neutre",
        item_type="bareme_imposition",
        libelle="Prélèvement à la Source (PAS) - Grille de taux par défaut",
        sections_or_valeurs=sections,
        generator="PAS/PAS_AI.py",
        source_url=cited_url,
        source_label="BOFIP — barème PAS (Sonar par zone, tableau officiel)",
        citation_url=cited_url,
        citation_date=cited_date,
        method="ai_web_search",
    )
    if payload is None:
        print("ERREUR CRITIQUE: payload PAS IA invalide (citation).", file=sys.stderr)
        sys.exit(1)
    emit_ai_payload_or_exit(payload, "pas_taux_neutre")


if __name__ == "__main__":
    main()
