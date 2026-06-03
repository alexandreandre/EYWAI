# scripts/SMIC/SMIC.py

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

_SCRAPING = Path(__file__).resolve().parent.parent
if str(_SCRAPING) not in sys.path:
    sys.path.insert(0, str(_SCRAPING))

from bs4 import BeautifulSoup

from core.http import build_session, fetch_html  # noqa: E402
from core.urssaf_parser import (  # noqa: E402
    UrssafTableSegment,
    iter_segments_from_soup,
    parse_french_amount,
    select_applicable_segment,
    smic_monthly_hours,
)

URL_URSSAF = (
    "https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html"
)

# Réexport pour les tests existants
parse_montant = parse_french_amount


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _smic_horaire_from_segment(segment: UrssafTableSegment) -> dict[str, float]:
    """Extrait les taux horaires SMIC d'un segment cohérent."""
    general: Optional[float] = None
    jeune_17: Optional[float] = None
    jeune_moins_17: Optional[float] = None
    mensuel: Optional[float] = None

    for label, val in segment.label_values.items():
        if "mensuel" in label and val > 500:
            if mensuel is None or val > mensuel:
                mensuel = val
            continue
        if "smic horaire brut" not in label:
            continue
        if "moins de 17" in label:
            jeune_moins_17 = val
        elif "17" in label:
            jeune_17 = val
        elif general is None:
            general = val

    if general is None:
        raise ValueError("Smic horaire brut introuvable dans le segment applicable")

    if jeune_17 is None:
        jeune_17 = round(general * 0.90, 2)
    if jeune_moins_17 is None:
        jeune_moins_17 = round(general * 0.80, 2)

    jeune_17 = min(jeune_17, general)
    jeune_moins_17 = min(jeune_moins_17, jeune_17)

    if mensuel is None:
        mensuel = round(general * smic_monthly_hours(), 2)

    return {
        "smic_horaire_brut": general,
        "smic_mensuel_brut": mensuel,
        "cas_general": general,
        "jeune_17_ans": jeune_17,
        "jeune_moins_17_ans": jeune_moins_17,
    }


def fetch_soup() -> BeautifulSoup:
    """Charge la page URSSAF SMIC (partagée primary + Sonar)."""
    html = fetch_html(URL_URSSAF, timeout=20, session=build_session())
    return BeautifulSoup(html, "html.parser")


def applicable_segment_table_text(
    soup: BeautifulSoup,
    *,
    reference_date: Optional[date] = None,
) -> str:
    """Texte du segment métropole applicable — contexte injecté pour Sonar."""
    ref = reference_date or datetime.now().date()
    segments = iter_segments_from_soup(
        soup, default_year=ref.year, reference_date=ref
    )
    segment = select_applicable_segment(
        segments,
        reference_date=ref,
        target_year=ref.year,
        prefer_mainland=True,
    )
    if segment is None:
        return ""
    lines = [
        f"Barème SMIC métropole URSSAF — révision du "
        f"{segment.effective_from.strftime('%d/%m/%Y')}",
        "Utilise UNIQUEMENT ce segment (pas Mayotte, pas les révisions antérieures).",
        "",
    ]
    for lk, lv in segment.label_values.items():
        lines.append(f"- {lk} : {lv} €")
    return "\n".join(lines)


def extract_smic_data(
    soup: BeautifulSoup,
    *,
    reference_date: Optional[date] = None,
) -> dict:
    """
    Extrait le SMIC métropole en vigueur à reference_date (révision URSSAF la plus récente).
    """
    ref = reference_date or datetime.now().date()
    segments = iter_segments_from_soup(
        soup, default_year=ref.year, reference_date=ref
    )
    segment = select_applicable_segment(
        segments,
        reference_date=ref,
        target_year=ref.year,
        prefer_mainland=True,
    )
    if segment is None:
        raise ValueError("Aucun segment SMIC applicable trouvé sur la page URSSAF")

    rates = _smic_horaire_from_segment(segment)
    return {
        **rates,
        "annee": segment.year,
        "source": "URSSAF",
        "effective_from": segment.effective_from.isoformat(),
    }


def get_tous_les_smic() -> dict | None:
    try:
        print(f"Scraping de l'URL : {URL_URSSAF}...", file=sys.stderr)
        soup = fetch_soup()
        data = extract_smic_data(soup)

        print(
            f"  - SMIC horaire brut (réf.): {data['smic_horaire_brut']} € | "
            f"mensuel: {data['smic_mensuel_brut']} € | année: {data['annee']} | "
            f"effet: {data.get('effective_from', '?')}",
            file=sys.stderr,
        )
        print(
            f"  - Par cas: général={data['cas_general']}, "
            f"17–18={data['jeune_17_ans']}, <17={data['jeune_moins_17_ans']}",
            file=sys.stderr,
        )

        sections = {k: v for k, v in data.items() if k != "source"}
        return sections

    except Exception as e:
        print(f"ERREUR : Le scraping a échoué. Raison : {e}", file=sys.stderr)
        return None


def main():
    smic_data = get_tous_les_smic()

    if not smic_data:
        print(
            "ERREUR CRITIQUE: Le scraping du SMIC a échoué ou n'a retourné aucune donnée.",
            file=sys.stderr,
        )
        sys.exit(1)

    payload = {
        "id": "smic_horaire",
        "type": "bareme_horaire",
        "libelle": "Salaire Minimum Interprofessionnel de Croissance (SMIC) - Taux horaire",
        "sections": smic_data,
        "meta": {
            "source": [
                {"url": URL_URSSAF, "label": "URSSAF - Montant du Smic", "date_doc": ""}
            ],
            "scraped_at": iso_now(),
            "generator": "scripts/SMIC/SMIC.py",
            "method": "primary",
        },
    }

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
