#!/usr/bin/env python3
"""Source IA — cotisations AGIRC-ARRCO (témoin Sonar, page officielle)."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from core.ai_extractor import (  # noqa: E402
    extract_with_web_search,
    is_official_citation_url,
    last_citation,
)
from core.year_utils import current_year  # noqa: E402

URL = (
    "https://www.agirc-arrco.fr/entreprises/mon-entreprise/calculer-et-declarer/"
    "le-calcul-des-cotisations-de-retraite-complementaire/"
)

RETRAITE_CET_KEYS = [
    "retraite_comp_t1_salarial",
    "retraite_comp_t1_patronal",
    "retraite_comp_t2_salarial",
    "retraite_comp_t2_patronal",
    "cet_salarial",
    "cet_patronal",
]

CEG_KEYS = [
    "ceg_t1_salarial",
    "ceg_t1_patronal",
    "ceg_t2_salarial",
    "ceg_t2_patronal",
]

APEC_KEYS = ["apec_salarial", "apec_patronal"]

EXPECTED_KEYS = RETRAITE_CET_KEYS + CEG_KEYS + APEC_KEYS

RETRAITE_CET_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": ["number", "null"]} for k in RETRAITE_CET_KEYS},
    "required": RETRAITE_CET_KEYS,
    "additionalProperties": False,
}

CEG_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": ["number", "null"]} for k in CEG_KEYS},
    "required": CEG_KEYS,
    "additionalProperties": False,
}

APEC_SCHEMA = {
    "type": "object",
    "properties": {k: {"type": ["number", "null"]} for k in APEC_KEYS},
    "required": APEC_KEYS,
    "additionalProperties": False,
}


def _to_rate(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    # Sonar renvoie parfois la fraction (0.0315) ou le % (3.15) ; APEC ~0.00024.
    if 0 < x < 0.02:
        return round(x, 6)
    return round(x / 100.0, 6)


def _build_items(bundle: dict) -> list[dict]:
    def add(id_: str, libelle: str, base: str, s: str, p: str) -> dict:
        return {
            "id": id_,
            "libelle": libelle,
            "base": base,
            "valeurs": {"salarial": bundle.get(s), "patronal": bundle.get(p)},
        }

    return [
        add(
            "retraite_comp_t1",
            "Retraite Complémentaire Tranche 1 (AGIRC-ARRCO)",
            "plafond_ss",
            "retraite_comp_t1_salarial",
            "retraite_comp_t1_patronal",
        ),
        add(
            "retraite_comp_t2",
            "Retraite Complémentaire Tranche 2 (AGIRC-ARRCO)",
            "tranche_2",
            "retraite_comp_t2_salarial",
            "retraite_comp_t2_patronal",
        ),
        add(
            "ceg_t1",
            "Contribution d'Équilibre Général (CEG) T1",
            "plafond_ss",
            "ceg_t1_salarial",
            "ceg_t1_patronal",
        ),
        add(
            "ceg_t2",
            "Contribution d'Équilibre Général (CEG) T2",
            "tranche_2",
            "ceg_t2_salarial",
            "ceg_t2_patronal",
        ),
        add(
            "cet",
            "Contribution d'Équilibre Technique (CET)",
            "brut_sup_plafond",
            "cet_salarial",
            "cet_patronal",
        ),
        add(
            "apec",
            "Cotisation APEC (Cadres)",
            "brut_cadre_4_plafonds",
            "apec_salarial",
            "apec_patronal",
        ),
    ]


def _ceg_rates_coherent(bundle: dict) -> bool:
    """Détecte la confusion fréquente T1 patronal (1,29 %) → T2 salarial."""
    t1s = bundle.get("ceg_t1_salarial")
    t1p = bundle.get("ceg_t1_patronal")
    t2s = bundle.get("ceg_t2_salarial")
    t2p = bundle.get("ceg_t2_patronal")
    if None in (t1s, t1p, t2s, t2p):
        return False
    if not (t1s < t1p and t2s < t2p and t1s < t2s and t1p < t2p):
        return False
    if abs(t2s - t1p) < 1e-5:
        return False
    return True


def _extract_ceg(cy: int) -> dict | None:
    """Passage dédié : Sonar mélange souvent CEG T1/T2 dans l'appel global."""
    for attempt in range(1, 4):
        raw = extract_with_web_search(
            task_prompt=(
                f"Sur {URL} (barème {cy}), tableau « Contribution d'équilibre "
                f"général (CEG) » UNIQUEMENT — pas retraite, pas CET, pas APEC.\n"
                f"- Ligne « Tranche 1 » : ceg_t1_salarial et ceg_t1_patronal "
                f"(ex. 0,86 % et 1,29 % en pourcentage brut : 0.86 et 1.29).\n"
                f"- Ligne « Tranche 2 » : ceg_t2_salarial et ceg_t2_patronal "
                f"(ex. 1,08 % et 1,62 % : 1.08 et 1.62).\n"
                f"Ne pas confondre : le taux patronal T1 (1,29) n'est PAS "
                f"ceg_t2_salarial. ceg_t2_salarial = part salariale tranche 2."
                + (f" (tentative {attempt}/3)" if attempt > 1 else "")
            ),
            json_schema=CEG_SCHEMA,
            schema_name="agirc_arrco_ceg",
            include_domains=["agirc-arrco.fr"],
        )
        if not raw:
            continue
        bundle = {k: _to_rate(raw.get(k)) for k in CEG_KEYS}
        if _ceg_rates_coherent(bundle):
            return bundle
    return None


def _extract_apec(cy: int) -> dict | None:
    """Second passage ciblé : Sonar omet souvent l'APEC dans l'appel global."""
    return extract_with_web_search(
        task_prompt=(
            f"Sur la page agirc-arrco.fr « calcul des cotisations retraite complémentaire », "
            f"extrais UNIQUEMENT les taux de la cotisation APEC (cadres) en vigueur en {cy} : "
            f"apec_salarial et apec_patronal (en %, ex. 0.024 et 0.036). "
            f"C'est une table séparée intitulée « Cotisation APEC »."
        ),
        json_schema=APEC_SCHEMA,
        schema_name="agirc_arrco_apec",
        include_domains=["agirc-arrco.fr"],
    )


def main() -> None:
    cy = current_year()
    data = extract_with_web_search(
        task_prompt=(
            f"Extrais les taux AGIRC-ARRCO applicables en {cy} depuis "
            f"{URL} : retraite complémentaire T1/T2 et CET "
            f"(parts salariale et patronale). Renvoie chaque valeur en pourcentage "
            f"(ex: 3.15 pour 3,15 %). Ne pas inclure CEG ni APEC."
        ),
        json_schema=RETRAITE_CET_SCHEMA,
        schema_name="agirc_arrco_retraite_cet",
        include_domains=["agirc-arrco.fr", "legifrance.gouv.fr"],
    )
    if not data:
        print("ERREUR CRITIQUE: extraction IA AGIRC-ARRCO échouée.", file=sys.stderr)
        sys.exit(1)

    citation_after_core = dict(last_citation())

    ceg_data = _extract_ceg(cy)
    if not ceg_data:
        print(
            "ERREUR CRITIQUE: extraction CEG IA incohérente ou incomplète.",
            file=sys.stderr,
        )
        sys.exit(1)
    data.update(ceg_data)

    apec_data = _extract_apec(cy)
    if apec_data:
        data.update(apec_data)

    # Le 2e appel (APEC) peut écraser last_citation sans date — garder la 1re citation valide.
    citation = dict(last_citation())
    if not citation.get("date") and citation_after_core.get("date"):
        citation = citation_after_core
    cited_url = citation.get("url") or URL
    cited_date = citation.get("date") or ""
    if is_official_citation_url(cited_url) and not cited_date:
        # Barème annuel : date de repli si Sonar fournit l'URL officielle sans date.
        cited_date = f"01/01/{cy}"
    if not is_official_citation_url(cited_url) or not cited_date:
        print(
            "ERREUR CRITIQUE: citation officielle datée manquante — extraction IA rejetée.",
            file=sys.stderr,
        )
        sys.exit(1)

    bundle = {k: _to_rate(data.get(k)) for k in EXPECTED_KEYS}
    missing = [k for k in EXPECTED_KEYS if bundle.get(k) is None]
    if missing:
        print(
            f"ERREUR CRITIQUE: taux AGIRC-ARRCO incomplets ({', '.join(missing)}).",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "agirc_arrco_bundle",
        "type": "cotisation_bundle",
        "items": _build_items(bundle),
        "meta": {
            "source": [
                {
                    "url": cited_url,
                    "label": "Agirc-Arrco (IA web)",
                    "date_doc": cited_date,
                }
            ],
            "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": "AGIRC-ARRCO/AGIRC-ARRCO_AI.py",
            "method": "ai_web_search",
        },
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
