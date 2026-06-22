# Helpers partagés pour l'orchestration bulletin heures et forfait (ex-generateur_fiche_paie*.py).
# Utilisés uniquement par payslip_run_heures et payslip_run_forfait.
from __future__ import annotations
from app.core.logging import get_logger, log_payroll_debug

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.modules.payroll.engine.reference_remuneration import mettre_a_jour_brut_reference_cumul

import calendar

from app.modules.payroll.engine.contexte import ContextePaie


logger = get_logger("modules.payroll.documents.payslip_run_common")

def _get_end_date_for_month(
    target_annee: int, target_mois: int, jour_cible: int, occurrence_cible: int
) -> date:
    """
    Trouve une date en se basant sur un jour de la semaine et son occurrence dans le mois.
    jour_cible: 0 pour Lundi, ..., 6 pour Dimanche.
    occurrence_cible: 1 pour le premier, -1 pour le dernier.
    """
    _, num_days = calendar.monthrange(target_annee, target_mois)
    jours_trouves = [
        date(target_annee, target_mois, day)
        for day in range(1, num_days + 1)
        if date(target_annee, target_mois, day).weekday() == jour_cible
    ]
    if not jours_trouves:
        raise ValueError(
            f"Aucun jour correspondant au jour {jour_cible} trouvé pour {target_mois}/{target_annee}."
        )
    try:
        if occurrence_cible > 0:
            return jours_trouves[occurrence_cible - 1]
        return jours_trouves[occurrence_cible]
    except IndexError:
        raise ValueError(
            f"L'occurrence {occurrence_cible} est invalide pour le mois de {target_mois}/{target_annee}."
        )


def definir_periode_de_paie(
    contexte: ContextePaie, annee: int, mois: int
) -> tuple[date, date]:
    """
    Détermine la période de paie en lisant les règles depuis la configuration de l'entreprise.
    La période de travail s'arrête le dimanche de la semaine du jour de référence.
    """
    regles_paie = contexte.entreprise.get("parametres_paie", {}).get(
        "periode_de_paie", {}
    )
    jour_reference = regles_paie.get("jour_de_fin", 4)
    occurrence_reference = regles_paie.get("occurrence", -2)

    date_de_reference = _get_end_date_for_month(
        annee, mois, jour_reference, occurrence_reference
    )
    decalage_vers_dimanche = 6 - date_de_reference.weekday()
    date_fin_periode = date_de_reference + timedelta(days=decalage_vers_dimanche)

    mois_precedent = mois - 1 if mois > 1 else 12
    annee_precedente = annee if mois > 1 else annee - 1
    date_de_reference_precedente = _get_end_date_for_month(
        annee_precedente, mois_precedent, jour_reference, occurrence_reference
    )
    decalage_vers_dimanche_precedent = 6 - date_de_reference_precedente.weekday()
    date_fin_periode_precedente = date_de_reference_precedente + timedelta(
        days=decalage_vers_dimanche_precedent
    )
    date_debut_periode = date_fin_periode_precedente + timedelta(days=1)
    return date_debut_periode, date_fin_periode


def mettre_a_jour_cumuls(
    contexte: ContextePaie,
    salaire_brut_mois: float,
    remuneration_hs_mois: float,
    resultats_nets_mois: dict,
    reduction_generale_mois: dict,
    mois: int,
    smic_mois: float,
    pss_mois: float,
    chemin_employe: Path,
) -> None:
    """Écrit le fichier cumuls du mois avec les valeurs du bulletin."""
    nouveaux_cumuls_data = json.loads(json.dumps(contexte.cumuls))
    nouveau_fichier_path = chemin_employe / "cumuls" / f"{mois:02d}.json"
    nouveaux_cumuls_data.setdefault("periode", {})["dernier_mois_calcule"] = mois
    cumuls = nouveaux_cumuls_data.setdefault("cumuls", {})

    cumuls["brut_total"] = cumuls.get("brut_total", 0.0) + round(salaire_brut_mois, 2)
    cumuls["net_imposable"] = cumuls.get("net_imposable", 0.0) + round(
        resultats_nets_mois.get("net_imposable", 0.0), 2
    )
    cumuls["impot_preleve_a_la_source"] = cumuls.get(
        "impot_preleve_a_la_source", 0.0
    ) + round(resultats_nets_mois.get("montant_impot_pas", 0.0), 2)
    cumuls["heures_supplementaires_remunerees"] = cumuls.get(
        "heures_supplementaires_remunerees", 0.0
    ) + round(remuneration_hs_mois, 2)
    cumuls.setdefault("heures_remunerees", 0.0)

    if reduction_generale_mois:
        nouveau_total = reduction_generale_mois.get(
            "valeur_cumulative_a_enregistrer", 0.0
        )
        cumuls["reduction_generale_patronale"] = -nouveau_total

    start_month = 6
    try:
        company_id = getattr(contexte, "company_id", None)
        if company_id:
            from app.modules.absences.infrastructure.leave_settings_repository import (
                get_leave_policy,
            )

            start_month = get_leave_policy(str(company_id)).cp_reference_period_start_month
    except Exception:
        pass

    annee = getattr(contexte, "year", None) or getattr(contexte, "annee_paie", None)
    if annee is None and isinstance(nouveaux_cumuls_data.get("periode"), dict):
        annee = nouveaux_cumuls_data["periode"].get("annee")
    ref_year = int(annee) if annee else date.today().year
    _, last_day = calendar.monthrange(ref_year, mois)
    mettre_a_jour_brut_reference_cumul(
        nouveaux_cumuls_data,
        round(salaire_brut_mois, 2),
        date(ref_year, mois, last_day),
        start_month=start_month,
    )

    nouveau_fichier_path.parent.mkdir(parents=True, exist_ok=True)
    with open(nouveau_fichier_path, "w", encoding="utf-8") as f:
        json.dump(nouveaux_cumuls_data, f, indent=2, ensure_ascii=False)
    log_payroll_debug(logger, f'INFO: Cumuls écrits dans {nouveau_fichier_path}')


def creer_calendrier_etendu(
    chemin_employe: Path, date_debut_periode: date, date_fin_periode: date
) -> list:
    """Charge les événements de paie des fichiers evenements_paie pour la période."""
    calendrier_final = []
    mois_a_charger = set()
    current_date = date_debut_periode
    while current_date <= date_fin_periode:
        mois_a_charger.add((current_date.year, current_date.month))
        current_date = (current_date.replace(day=28) + timedelta(days=4)).replace(day=1)

    for annee, mois in mois_a_charger:
        chemin_fichier = chemin_employe / "evenements_paie" / f"{mois:02d}.json"
        if chemin_fichier.exists():
            data = json.loads(chemin_fichier.read_text(encoding="utf-8"))
            for jour_data in data.get("calendrier_analyse", []):
                jour_data["date_complete"] = date(
                    annee, mois, jour_data["jour"]
                ).isoformat()
                calendrier_final.append(jour_data)
        else:
            logger.warning(f'AVERTISSEMENT: Fichier événements {mois:02d}.json non trouvé.')

    return sorted(calendrier_final, key=lambda j: j["date_complete"])


def resolve_exit_state_for_payslip(
    employee_id: str,
    year: int,
    month: int,
    supabase_client: Any | None = None,
) -> tuple[dict | None, bool]:
    """
    Retourne (indemnités calculées, blocage ICCP auto).

    block_iccp_cdd=True si un départ tombe sur ce mois mais les indemnités
    n'ont pas encore été calculées (évite un ICCP 10e seul incorrect).
    """
    if not employee_id:
        return None, False

    try:
        from app.core.database import supabase as default_supabase

        sb = supabase_client or default_supabase
        resp = (
            sb.table("employee_exits")
            .select("id, last_working_day, status, calculated_indemnities")
            .eq("employee_id", employee_id)
            .not_.in_("status", ["cancelled", "canceled", "annule", "annulee"])
            .order("last_working_day", desc=True)
            .limit(5)
            .execute()
        )
        rows = resp.data or []
    except Exception as exc:
        log_payroll_debug(
            logger,
            f"Indemnités de sortie non résolues pour bulletin ({employee_id}): {exc}",
        )
        return None, False

    for row in rows:
        last_day_raw = row.get("last_working_day")
        if not last_day_raw:
            continue
        if isinstance(last_day_raw, str):
            last_day = date.fromisoformat(last_day_raw[:10])
        else:
            last_day = last_day_raw
        if last_day.year != year or last_day.month != month:
            continue

        indemnities = row.get("calculated_indemnities")
        if indemnities:
            return indemnities, False
        return None, True

    return None, False


def resolve_exit_indemnities_for_payslip(
    employee_id: str,
    year: int,
    month: int,
    supabase_client: Any | None = None,
) -> dict | None:
    """Retourne les indemnités de sortie calculées si un départ tombe sur ce mois de paie."""
    indemnities, _ = resolve_exit_state_for_payslip(
        employee_id, year, month, supabase_client
    )
    return indemnities


def prefetch_jours_maintien_prime(
    *,
    company_id: str | None,
    contexte: ContextePaie,
    arret_data: dict[str, Any] | None,
    date_debut_periode: date,
    date_fin_periode: date,
) -> set[int]:
    """Pré-calcule les jours du mois avec maintien (prorata prime d'ancienneté)."""
    if not company_id or not arret_data:
        return set()
    try:
        from app.modules.maintenance_settings.application.queries import (
            get_maintenance_settings,
        )
        from app.modules.payroll.engine.maintien_salaire_service import (
            compute_jours_avec_maintien_mois,
        )

        settings_maintien = get_maintenance_settings(company_id)
        settings_dict = settings_maintien.model_dump(mode="json")
        return compute_jours_avec_maintien_mois(
            arret_data,
            contexte,
            settings_dict,
            date_debut_periode,
            date_fin_periode,
        )
    except Exception as exc:
        logger.warning(
            "Jours maintien prime non calculés (company_id=%s): %s",
            company_id,
            exc,
        )
        return set()
