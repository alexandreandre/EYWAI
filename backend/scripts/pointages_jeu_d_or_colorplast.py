"""Jeu d'or : relire les feuilles Colorplast S27–S30 avec le pipeline réel et compter.

Les quatre feuilles de juillet 2026 (`data/colorplast/pointages/2026-07/`) ont
été transcrites case par case (`tests/fixtures/timesheets/colorplast_2026_s27_s30_attendu.json`,
120 cases : heures pause déduite, `null` pour un jour sans heures, « illisible »
pour les deux cases de Marion à demander à Gaëlle). Ce script passe chaque
feuille dans `extract_timesheet_hybrid` avec la semaine ancrée et les réglages de
pause de la société, comme le fait l'import, puis compare.

Il appelle le modèle de vision (clé OpenRouter du `.env`) : à lancer en
arrière-plan, pas sous le timeout de l'outil. Le résultat brut est écrit dans
`--sortie` pour analyse (jours lus, avertissements de page).

Usage :
    python -m scripts.pointages_jeu_d_or_colorplast [--feuille semaine-29.pdf] [--sortie jeu_d_or.json]
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RACINE = Path(__file__).resolve().parents[2]
FEUILLES = RACINE / "data" / "colorplast" / "pointages" / "2026-07"
ATTENDU = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "timesheets" / "colorplast_2026_s27_s30_attendu.json"
SOCIETE = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE, MOIS = 2026, 7

Verdict = tuple[str, Any, Any, str]


def _norme(valeur: Any) -> float:
    return 0.0 if valeur is None else round(float(valeur), 2)


def comparer(attendu: dict[str, Any], lu: dict[str, Any]) -> list[Verdict]:
    """Par date ISO : (date, attendu, lu, verdict) avec juste|faux|manquant|illisible.

    `null` attendu et 0 lu valent pareil : pas d'heures ce jour-là.
    """
    lignes: list[Verdict] = []
    for jour in sorted(attendu):
        valeur = attendu[jour]
        if valeur == "illisible":
            lignes.append((jour, valeur, lu.get(jour), "illisible"))
        elif jour not in lu and _norme(valeur) == 0.0:
            # Férié hachuré, case barrée : le modèle ne rend souvent aucun jour.
            lignes.append((jour, valeur, None, "vide"))
        elif jour not in lu:
            lignes.append((jour, valeur, None, "manquant"))
        elif abs(_norme(lu[jour]) - _norme(valeur)) < 0.01:
            lignes.append((jour, valeur, lu[jour], "juste"))
        else:
            lignes.append((jour, valeur, lu[jour], "faux"))
    return lignes


def bilan(lignes: list[Verdict]) -> tuple[int, int, int]:
    """(justes, fausses — manquant compris —, illisibles)."""
    justes = sum(1 for ligne in lignes if ligne[3] in ("juste", "vide"))
    illisibles = sum(1 for ligne in lignes if ligne[3] == "illisible")
    return justes, len(lignes) - justes - illisibles, illisibles


def _extraire(fichier: str, contenu: bytes, lundi: date):
    from app.modules.schedules.application.timesheet_hybrid_extract import (
        extract_timesheet_hybrid,
    )
    from app.modules.schedules.application.timesheet_period import (
        format_week_anchor_context,
    )
    from app.modules.schedules.infrastructure import punch_accounting_repository

    return extract_timesheet_hybrid(
        file_content=contenu,
        filename=fichier,
        year=ANNEE,
        month=MOIS,
        known_matricules=[],
        week_anchor_context=format_week_anchor_context(lundi, ANNEE, MOIS),
        week_anchor_date=lundi,
        punch_settings=punch_accounting_repository.get_settings(SOCIETE),
    )


def _lire_feuille(fichier: str, lundi: date) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    from app.modules.schedules.application import timesheet_hybrid_extract as module

    reponses_modele: list[dict[str, Any]] = []

    def _capture(nom_original: str):
        original = getattr(module, nom_original)

        def enveloppe(*args: Any, **kwargs: Any):
            reponse = original(*args, **kwargs)
            reponses_modele.append(
                {"canal": nom_original, "donnees": getattr(reponse, "data", None)}
            )
            return reponse

        return original, enveloppe

    originaux = {}
    for nom_fonction in ("extract_structured_json_from_image", "extract_structured_json"):
        original, enveloppe = _capture(nom_fonction)
        originaux[nom_fonction] = original
        setattr(module, nom_fonction, enveloppe)

    # Et ce que le rendu a décidé pour l'image (sens, taille) avant tout appel.
    orientations: list[dict[str, Any]] = []
    rendu_original = module.render_document_pages

    def rendu_trace(*args: Any, **kwargs: Any):
        rendu = rendu_original(*args, **kwargs)
        for page in rendu.pages:
            orientations.append(
                {
                    "page": page.page_index,
                    "angle": page.orientation_angle,
                    "source": page.orientation_source,
                    "octets": len(page.png_bytes or b""),
                }
            )
        return rendu

    originaux["render_document_pages"] = rendu_original
    module.render_document_pages = rendu_trace

    contenu = (FEUILLES / fichier).read_bytes()
    try:
        resultat = _extraire(fichier, contenu, lundi)
    finally:
        for nom_fonction, original in originaux.items():
            setattr(module, nom_fonction, original)
    lu: dict[str, dict[str, Any]] = {}
    for bloc in resultat.parse_result.employees:
        cases = lu.setdefault(bloc.raw_name.strip().upper(), {})
        for d in bloc.days:
            cases[date(d.year or ANNEE, d.month or MOIS, d.jour).isoformat()] = d.heures
    brut = {
        "fichier": fichier,
        "methode": resultat.extraction_method,
        "tokens": resultat.tokens_used,
        "avertissements": list(resultat.warnings),
        "orientation": orientations,
        "modele": reponses_modele,
        "pages": [
            {
                "index": p.page_index,
                "avertissements": list(p.warnings),
                "salaries": [
                    {"raw_name": e.raw_name, "confiance": e.confidence, "jours": e.days, "avertissements": e.warnings}
                    for e in p.employees
                ],
            }
            for p in resultat.page_results
        ],
        "blocs": [
            {"raw_name": b.raw_name, "avertissements": b.parse_warnings, "jours": [(d.jour, d.month, d.heures) for d in b.days]}
            for b in resultat.parse_result.employees
        ],
    }
    return lu, brut


def main(argv: list[str]) -> int:
    from app.core import settings as _charge_env  # noqa: F401  (charge le .env)
    from app.shared.infrastructure.ai.client import is_llm_configured

    if not is_llm_configured():
        print("OPENROUTER_API_KEY absente : le jeu d'or ne peut pas tourner.")
        return 2

    feuille_voulue = argv[argv.index("--feuille") + 1] if "--feuille" in argv else None
    sortie = Path(argv[argv.index("--sortie") + 1]) if "--sortie" in argv else None
    attendu = json.loads(ATTENDU.read_text())

    total: list[Verdict] = []
    bruts: list[dict[str, Any]] = []
    for fichier, bloc in attendu.items():
        if feuille_voulue and fichier != feuille_voulue:
            continue
        lundi = date.fromisoformat(bloc["lundi"])
        print(f"\n=== {fichier} — semaine du {lundi:%d/%m} au {lundi + timedelta(days=4):%d/%m}")
        lu, brut = _lire_feuille(fichier, lundi)
        bruts.append(brut)
        for nom, cases in bloc["salaries"].items():
            lignes = comparer(cases, lu.get(nom, {}))
            total.extend(lignes)
            rendu = " ".join(
                f"{_fmt(a)}→{_fmt(lu_)}{'' if v in ('juste', 'vide') else '✗' if v in ('faux', 'manquant') else '?'}"
                for _, a, lu_, v in lignes
            )
            print(f"  {nom:9s} {rendu}")
        for avert in brut["avertissements"] + [a for p in brut["pages"] for a in p["avertissements"]]:
            print(f"  ! {avert}")
        for o in brut["orientation"]:
            print(f"  image page {o['page']} : angle {o['angle']}° ({o['source']}), {o['octets'] // 1024} Ko")
        print(f"  tokens : {brut['tokens']}")

    justes, fausses, illisibles = bilan(total)
    print(f"\nBilan : {justes} justes, {fausses} fausses, {illisibles} illisibles sur {len(total)} cases")
    if sortie:
        sortie.write_text(json.dumps({"bilan": [justes, fausses, illisibles], "cases": total, "brut": bruts}, ensure_ascii=False, indent=1, default=str))
        print(f"résultat brut : {sortie}")
    return 0


def _fmt(valeur: Any) -> str:
    if valeur is None:
        return "·"
    if valeur == "illisible":
        return "?"
    return f"{float(valeur):g}"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
