"""
Fixtures pour les tests de comparaison payroll (données fictives).

Construit un répertoire employé minimal avec contrat, entreprise, saisies,
cumuls, calendriers, horaires, événements de paie pour un mois donné.
"""
from __future__ import annotations

import calendar
import json
from datetime import date
from pathlib import Path
from typing import Any


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def build_contrat_heures(employee_folder_name: str) -> dict:
    """Contrat minimal pour un employé au régime heures."""
    return {
        "salarie": {"nom": "Dupont", "prenom": "Jean", "nir": ""},
        "contrat": {
            "date_entree": "2024-01-01",
            "statut": "Non-Cadre",
            "emploi": "Employé",
            "temps_travail": {"duree_hebdomadaire": 35.0},
        },
        "remuneration": {
            "salaire_de_base": {"valeur": 2000.0},
            "classification_conventionnelle": {},
            "avantages_en_nature": {},
        },
        "specificites_paie": {
            "prevoyance": "NON",
            "prelevement_a_la_source": {"taux": 0},
            "is_alsace_moselle": False,
        },
    }


def build_contrat_forfait(employee_folder_name: str) -> dict:
    """Contrat minimal pour un employé forfait jour."""
    return {
        "salarie": {"nom": "Martin", "prenom": "Marie", "nir": ""},
        "contrat": {
            "date_entree": "2024-01-01",
            "statut": "Cadre au forfait jour",
            "emploi": "Cadre",
            "temps_travail": {"duree_hebdomadaire": 35.0},
        },
        "remuneration": {
            "salaire_de_base": {"valeur": 3500.0},
            "classification_conventionnelle": {},
            "avantages_en_nature": {},
        },
        "specificites_paie": {
            "prevoyance": "NON",
            "prelevement_a_la_source": {"taux": 0},
            "is_alsace_moselle": False,
        },
    }


def build_entreprise(effectif: int = 10) -> dict:
    """Entreprise minimale avec période de paie (avant-dernier vendredi → dimanche)."""
    return {
        "entreprise": {
            "identification": {"raison_sociale": "Test SARL", "siren": "123456789"},
            "parametres_paie": {
                "effectif": effectif,
                "periode_de_paie": {"jour_de_fin": 4, "occurrence": -2},
            },
        }
    }


def build_saisie_mois(year: int, month: int, acompte: float = 0.0) -> dict:
    """Saisie du mois (primes vides, acompte optionnel)."""
    return {
        "periode": {"mois": month, "annee": year},
        "acompte": acompte,
        "primes": [],
        "notes_de_frais": [],
        "autres": [],
    }


def build_cumuls_prev_month() -> dict:
    """Cumuls du mois précédent (vides)."""
    return {"cumuls": {}, "periode": {}}


def build_calendrier_prevu_heures(year: int, month: int, heures_par_jour: float = 7.0) -> dict:
    """Calendrier prévu pour un mois (jours ouvrés = travail avec heures_prevues)."""
    _, num_days = calendar.monthrange(year, month)
    calendrier = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5:  # lun-ven
            calendrier.append({
                "jour": day,
                "type": "travail",
                "heures_prevues": heures_par_jour,
            })
        else:
            calendrier.append({"jour": day, "type": "weekend", "heures_prevues": 0})
    return {"calendrier_prevu": calendrier}


def build_calendrier_prevu_forfait(year: int, month: int) -> dict:
    """Calendrier prévu forfait jour (1 = jour travaillé)."""
    _, num_days = calendar.monthrange(year, month)
    calendrier = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5:
            calendrier.append({"jour": day, "type": "travail", "heures_prevues": 1.0})
        else:
            calendrier.append({"jour": day, "type": "weekend", "heures_prevues": 0})
    return {"calendrier_prevu": calendrier}


def build_horaires_reels_heures(year: int, month: int, heures_par_jour: float = 7.0) -> dict:
    """Horaires réels (calendrier) pour régime heures."""
    _, num_days = calendar.monthrange(year, month)
    calendrier = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5:
            calendrier.append({"jour": day, "type": "travail", "heures": heures_par_jour})
        else:
            calendrier.append({"jour": day, "type": "weekend", "heures": 0})
    return {"calendrier": calendrier}


def build_horaires_reels_forfait(year: int, month: int) -> dict:
    """Horaires réels forfait (calendrier avec type/heures)."""
    _, num_days = calendar.monthrange(year, month)
    calendrier = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5:
            calendrier.append({"jour": day, "type": "travail", "heures": 1.0})
        else:
            calendrier.append({"jour": day, "type": "weekend", "heures": 0})
    return {"calendrier": calendrier}


def build_evenements_paie_month(year: int, month: int, heures_par_jour: float = 7.0) -> dict:
    """Événements de paie pour un mois (calendrier_analyse avec type/jour/heures)."""
    _, num_days = calendar.monthrange(year, month)
    evenements = []
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() < 5:
            evenements.append({"jour": day, "type": "travail", "heures": heures_par_jour})
        else:
            evenements.append({"jour": day, "type": "weekend", "heures": 0})
    return {"calendrier_analyse": evenements}


def build_employee_fixture_dir(
    engine_root: Path,
    employee_name: str,
    year: int,
    month: int,
    mode: str = "heures",
    effectif: int = 10,
) -> Path:
    """
    Crée sous ``engine_root/data/employes/<employee_name>/`` (même contrat que
    ``payroll_engine_root()`` → typiquement ``app/runtime/payroll/``) tous les
    fichiers nécessaires pour une génération (contrat, entreprise, saisies,
    cumuls, calendriers, horaires, evenements_paie). Retourne le path du dossier
    employé.
    """
    data_dir = engine_root / "data"
    employes_dir = data_dir / "employes"
    employee_path = employes_dir / employee_name

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1

    # Entreprise (partagée) — écrasée à chaque appel
    _write_json(data_dir / "entreprise.json", build_entreprise(effectif))

    # Contrat
    if mode == "forfait":
        _write_json(employee_path / "contrat.json", build_contrat_forfait(employee_name))
    else:
        _write_json(employee_path / "contrat.json", build_contrat_heures(employee_name))

    # Saisie du mois
    _write_json(employee_path / "saisies" / f"{month:02d}.json", build_saisie_mois(year, month))

    # Cumuls mois précédent
    _write_json(employee_path / "cumuls" / f"{prev_month:02d}.json", build_cumuls_prev_month())

    # Calendrier prévu
    if mode == "forfait":
        _write_json(
            employee_path / "calendriers" / f"{month:02d}.json",
            build_calendrier_prevu_forfait(year, month),
        )
    else:
        _write_json(
            employee_path / "calendriers" / f"{month:02d}.json",
            build_calendrier_prevu_heures(year, month),
        )

    # Horaires réels
    if mode == "forfait":
        _write_json(
            employee_path / "horaires" / f"{month:02d}.json",
            build_horaires_reels_forfait(year, month),
        )
    else:
        _write_json(
            employee_path / "horaires" / f"{month:02d}.json",
            build_horaires_reels_heures(year, month),
        )

    # Événements de paie (pour période à cheval : mars + avril si month=4)
    for y, m in [(prev_year, prev_month), (year, month)]:
        if mode == "forfait":
            ev = build_evenements_paie_month(y, m, 1.0)
        else:
            ev = build_evenements_paie_month(y, m, 7.0)
        _write_json(employee_path / "evenements_paie" / f"{m:02d}.json", ev)

    return employee_path
