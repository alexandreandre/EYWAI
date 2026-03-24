"""
Commandes (cas d'usage écriture) du module schedules.

Délèguent au repository et aux providers (infrastructure), règles du domain.
Comportement identique à l'ancien router. Lève ScheduleAppError.
"""
import calendar as cal_mod
import json
import sys
import traceback
from datetime import date
from typing import Any, Dict, List, Tuple

from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.service import (
    get_employee_company_and_statut,
    normalize_actual_hours_for_employee,
    normalize_planned_calendar_for_employee,
)
from app.modules.schedules.domain import rules as domain_rules
from app.modules.schedules.domain.exceptions import ScheduleNotFoundError
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_prevu_from_planned_calendar,
    extract_calendrier_reel_from_actual_hours,
)
from app.modules.schedules.infrastructure.providers import (
    forfait_jour_provider,
    payroll_analyzer_provider,
)
from app.modules.schedules.infrastructure.queries import employee_company_reader
from app.modules.schedules.infrastructure.repository import schedule_repository


def update_planned_calendar(employee_id: str, payload: Any) -> Dict[str, str]:
    """
    Met à jour (ou crée) le calendrier prévu dans employee_schedules.
    payload : objet avec .year, .month, .calendrier_prevu (liste d'entrées Pydantic).
    """
    try:
        print(f"\n{'='*70}")
        print(f"🔵 POST /planned-calendar - DEBUT")
        print(f"{'='*70}")
        print(f"Employee ID: {employee_id}")
        print(f"Year: {payload.year}, Month: {payload.month}")
        print(f"Nombre d'entrées calendrier: {len(payload.calendrier_prevu)}")

        company_id, employee_statut = get_employee_company_and_statut(employee_id)
        print(f"Company ID récupéré: {company_id}")
        print(f"Statut employé: {employee_statut}")

        calendrier_prevu_raw = [entry.model_dump() for entry in payload.calendrier_prevu]
        calendrier_prevu_normalized = normalize_planned_calendar_for_employee(
            calendrier_prevu_raw, employee_statut
        )
        if domain_rules.is_forfait_jour(employee_statut):
            print(
                f"✅ Normalisation forfait jour appliquée: {len(calendrier_prevu_normalized)} entrées normalisées"
            )

        json_content = {
            "periode": {"mois": payload.month, "annee": payload.year},
            "calendrier_prevu": calendrier_prevu_normalized,
        }
        print(f"\n📦 JSON Content créé:")
        print(f"   - periode: {json_content['periode']}")
        print(f"   - calendrier_prevu: {len(json_content['calendrier_prevu'])} entrées")

        print(f"\n🔄 Tentative d'upsert avec on_conflict='employee_id,year,month'")
        print(f"   Données upsert: employee_id, company_id, year, month, planned_calendar")
        print(f"   Taille du calendrier: {len(calendrier_prevu_normalized)} entrées")

        schedule_repository.upsert_schedule(
            employee_id,
            company_id,
            payload.year,
            payload.month,
            planned_calendar=json_content,
        )

        print(f"\n✅ Upsert réussi!")
        print(f"{'='*70}\n")
        return {"status": "success", "message": "Planning prévisionnel enregistré."}

    except ScheduleAppError:
        raise
    except Exception as e:
        print(f"\n❌ ERREUR dans update_planned_calendar:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        traceback.print_exc()
        print(f"{'='*70}\n")
        raise ScheduleAppError("error", str(e), status_code=500) from e


def update_actual_hours(employee_id: str, payload: Any) -> Dict[str, str]:
    """
    Met à jour (ou crée) les heures réelles dans employee_schedules.
    payload : objet avec .year, .month, .calendrier_reel.
    """
    try:
        print(f"\n{'='*70}")
        print(f"🟢 POST /actual-hours - DEBUT")
        print(f"{'='*70}")
        print(f"Employee ID: {employee_id}")
        print(f"Year: {payload.year}, Month: {payload.month}")
        print(f"Nombre d'entrées calendrier réel: {len(payload.calendrier_reel)}")

        company_id, employee_statut = get_employee_company_and_statut(employee_id)
        print(f"Company ID récupéré: {company_id}")
        print(f"Statut employé: {employee_statut}")

        calendrier_reel_raw = [entry.model_dump() for entry in payload.calendrier_reel]
        calendrier_reel_normalized = normalize_actual_hours_for_employee(
            calendrier_reel_raw, employee_statut
        )
        if domain_rules.is_forfait_jour(employee_statut):
            print(
                f"✅ Normalisation forfait jour appliquée aux heures réelles: {len(calendrier_reel_normalized)} entrées normalisées"
            )

        json_content = {
            "periode": {"mois": payload.month, "annee": payload.year},
            "calendrier_reel": calendrier_reel_normalized,
        }
        print(f"\n📦 JSON Content créé:")
        print(f"   - periode: {json_content['periode']}")
        print(f"   - calendrier_reel: {len(json_content['calendrier_reel'])} entrées")

        print(f"\n🔄 Tentative d'upsert avec on_conflict='employee_id,year,month'")
        print(f"   Données upsert: employee_id, company_id, year, month, actual_hours")
        print(f"   Taille du calendrier réel: {len(calendrier_reel_normalized)} entrées")

        schedule_repository.upsert_schedule(
            employee_id,
            company_id,
            payload.year,
            payload.month,
            actual_hours=json_content,
        )

        print(f"\n✅ Upsert réussi!")
        print(f"{'='*70}\n")
        return {"status": "success", "message": "Heures réelles enregistrées."}

    except ScheduleAppError:
        raise
    except Exception as e:
        print(f"\n❌ ERREUR dans update_actual_hours:")
        print(f"   Type: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        traceback.print_exc()
        print(f"{'='*70}\n")
        raise ScheduleAppError("error", str(e), status_code=500) from e


def _dates_to_process(year: int, month: int) -> List[Dict[str, int]]:
    """Retourne [M-1, M, M+1] en (year, month)."""
    dates_to_process = []
    for i in [-1, 0, 1]:
        d = date(year, month, 15)
        target_month, target_year = (d.month + i, d.year)
        if target_month == 0:
            target_month, target_year = (12, target_year - 1)
        elif target_month == 13:
            target_month, target_year = (1, target_year + 1)
        dates_to_process.append({"year": target_year, "month": target_month})
    return dates_to_process


def _build_planned_actual_from_rows(
    rows: List[Dict[str, Any]], dates_to_process: List[Dict[str, int]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Construit planned_data_all_months et actual_data_all_months avec annee, mois sur chaque entrée."""
    db_data_map = {(row["year"], row["month"]): row for row in rows}
    planned_data_all_months = []
    actual_data_all_months = []
    for date_info in dates_to_process:
        y, m = date_info["year"], date_info["month"]
        db_row = db_data_map.get((y, m))
        if db_row:
            planned_list = extract_calendrier_prevu_from_planned_calendar(
                db_row.get("planned_calendar")
            )
            actual_list = extract_calendrier_reel_from_actual_hours(
                db_row.get("actual_hours")
            )
            for entry in planned_list:
                entry = dict(entry)
                entry.update({"annee": y, "mois": m})
                planned_data_all_months.append(entry)
            for entry in actual_list:
                entry = dict(entry)
                entry.update({"annee": y, "mois": m})
                actual_data_all_months.append(entry)
    return planned_data_all_months, actual_data_all_months


def calculate_payroll_events(employee_id: str, year: int, month: int) -> Dict[str, Any]:
    """
    Calcule les événements de paie pour un employé sur un mois (M-1, M, M+1).
    Utilise payroll_analyzer ou forfait jour selon le statut.
    """
    try:
        print(
            f"\n--- Début du calcul de paie pour l'employé {employee_id} ({month}/{year}) ---",
            file=sys.stderr,
        )

        employee_data = employee_company_reader.get_employee_for_payroll_events(
            employee_id
        )
        employee_name = employee_data["employee_folder_name"]
        duree_hebdo = employee_data.get("duree_hebdomadaire")
        employee_statut = employee_data.get("statut")
        company_id = employee_data.get("company_id")
        if not duree_hebdo:
            raise ScheduleAppError(
                "validation",
                "La durée hebdomadaire du contrat n'est pas définie.",
                status_code=400,
            )

        is_employee_forfait_jour = domain_rules.is_forfait_jour(employee_statut)
        if is_employee_forfait_jour:
            print(
                f"✅ Employé en forfait jour détecté (statut: {employee_statut})",
                file=sys.stderr,
            )

        date_debut_periode = None
        date_fin_periode = None
        if is_employee_forfait_jour and company_id:
            try:
                parametres_paie = employee_company_reader.get_company_parametres_paie(
                    company_id
                )
                if parametres_paie is not None:
                    date_debut_periode, date_fin_periode = (
                        forfait_jour_provider.definir_periode_de_paie(
                            parametres_paie, employee_statut, year, month
                        )
                    )
                    if date_debut_periode and date_fin_periode:
                        print(
                            f"✅ Période de paie calculée pour forfait jour : "
                            f"du {date_debut_periode.strftime('%d/%m/%Y')} au {date_fin_periode.strftime('%d/%m/%Y')}",
                            file=sys.stderr,
                        )
            except Exception as e:
                print(
                    f"⚠️ Impossible de calculer la période de paie pour le forfait jour: {e}. "
                    f"Utilisation du filtrage par mois.",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)

        dates_to_process = _dates_to_process(year, month)
        year_months = [(d["year"], d["month"]) for d in dates_to_process]
        rows = schedule_repository.get_schedules_for_months(
            employee_id, year_months
        )

        print("\n" + "=" * 20 + " ESPION 1 : DONNÉES BRUTES DE SUPABASE " + "=" * 20)
        try:
            print(json.dumps(rows, indent=2))
        except TypeError:
            print(rows)
        print("=" * 67 + "\n")
        print(
            f"-> Données de {len(rows)} mois récupérées depuis Supabase.",
            file=sys.stderr,
        )

        planned_data_all_months, actual_data_all_months = _build_planned_actual_from_rows(
            rows, dates_to_process
        )

        print(
            "\n"
            + "=" * 20
            + " ESPION 2 : DONNÉES PRÊTES POUR L'ANALYSEUR "
            + "=" * 20
        )
        print("Contenu de la variable 'planned_data_all_months' :")
        print(json.dumps(planned_data_all_months, indent=2))
        print("=" * 75 + "\n")

        if is_employee_forfait_jour:
            payroll_events_list = forfait_jour_provider.analyser_jours_forfait_du_mois(
                planned_data_all_months=planned_data_all_months,
                actual_data_all_months=actual_data_all_months,
                annee=year,
                mois=month,
                employee_name=employee_name,
                date_debut_periode=date_debut_periode,
                date_fin_periode=date_fin_periode,
            )
            if date_debut_periode and date_fin_periode:
                print(
                    f"✅ Analyseur forfait jour utilisé avec période de paie",
                    file=sys.stderr,
                )
            else:
                print(
                    f"✅ Analyseur forfait jour utilisé (filtrage par mois)",
                    file=sys.stderr,
                )
        else:
            payroll_events_list = payroll_analyzer_provider.analyser_horaires(
                planned_data_all_months=planned_data_all_months,
                actual_data_all_months=actual_data_all_months,
                duree_hebdo_contrat=duree_hebdo,
                annee=year,
                mois=month,
                employee_name=employee_name,
            )
            print(f"✅ Analyseur normal (heures) utilisé", file=sys.stderr)
        print(
            f"-> Analyse terminée : {len(payroll_events_list)} événements de paie générés.",
            file=sys.stderr,
        )

        result_json = {
            "periode": {"annee": year, "mois": month},
            "calendrier_analyse": payroll_events_list,
        }
        schedule_repository.update_payroll_events(
            employee_id, year, month, result_json
        )
        print(f"-> Résultat sauvegardé avec succès.", file=sys.stderr)

        return {
            "status": "success",
            "message": f"{len(payroll_events_list)} événements de paie calculés.",
        }

    except ScheduleAppError:
        raise
    except ScheduleNotFoundError as e:
        raise ScheduleAppError("not_found", str(e), status_code=404) from e
    except Exception as e:
        traceback.print_exc()
        raise ScheduleAppError("error", str(e), status_code=500) from e


def apply_schedule_model(request: Any, current_user: Any) -> Dict[str, Any]:
    """
    Applique un modèle de planning à plusieurs employés pour un mois donné.
    request : objet avec .employee_ids, .year, .month, .week_configs.
    current_user : objet avec .active_company_id, .has_rh_access_in_company(company_id).
    """
    company_id = current_user.active_company_id
    if not company_id:
        raise ScheduleAppError(
            "validation", "Aucune entreprise active", status_code=400
        )
    if not current_user.has_rh_access_in_company(company_id):
        raise ScheduleAppError(
            "forbidden", "Accès réservé aux RH", status_code=403
        )
    if not request.employee_ids:
        raise ScheduleAppError(
            "validation", "Aucun employé sélectionné", status_code=400
        )
    if request.month < 1 or request.month > 12:
        raise ScheduleAppError("validation", "Mois invalide", status_code=400)
    if request.year < 2020 or request.year > 2100:
        raise ScheduleAppError("validation", "Année invalide", status_code=400)

    try:
        num_days_in_month = cal_mod.monthrange(request.year, request.month)[1]
        first_day_of_month = date(request.year, request.month, 1)
        day_keys = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]

        for employee_id in request.employee_ids:
            try:
                company_id_emp, employee_statut = (
                    employee_company_reader.get_company_and_statut(employee_id)
                )
            except ScheduleNotFoundError:
                raise ScheduleAppError(
                    "not_found",
                    f"Employé {employee_id} non trouvé ou sans entreprise associée",
                    status_code=404,
                )
            is_employee_forfait_jour = domain_rules.is_forfait_jour(
                employee_statut
            )

            calendrier_prevu = []
            for day in range(1, num_days_in_month + 1):
                current_date = date(request.year, request.month, day)
                day_of_week = current_date.weekday()
                week_of_month = (
                    (day + first_day_of_month.weekday() - 1) // 7
                ) + 1
                week_number = min(week_of_month, 5)

                week_config = request.week_configs.get(week_number)
                if not week_config:
                    raise ScheduleAppError(
                        "validation",
                        f"Configuration manquante pour la semaine {week_number}",
                        status_code=400,
                    )

                day_key = day_keys[day_of_week]
                day_config = getattr(week_config, day_key)
                is_work_day = day_config.type in ["work", "travail"]
                if is_employee_forfait_jour:
                    heures_prevues = 1 if is_work_day else 0
                else:
                    heures_prevues = day_config.hours if is_work_day else 0

                calendar_entry = {
                    "jour": day,
                    "type": day_config.type,
                    "heures_prevues": heures_prevues,
                }
                calendrier_prevu.append(calendar_entry)

            planned_calendar_json = {"calendrier_prevu": calendrier_prevu}

            if schedule_repository.exists_schedule(
                employee_id, request.year, request.month
            ):
                schedule_repository.update_planned_calendar_only(
                    employee_id,
                    request.year,
                    request.month,
                    planned_calendar_json,
                )
            else:
                schedule_repository.insert_schedule(
                    employee_id,
                    company_id_emp,
                    request.year,
                    request.month,
                    planned_calendar_json,
                )

        return {
            "status": "success",
            "message": f"Le modèle a été appliqué à {len(request.employee_ids)} employé(s)",
            "details": {
                "year": request.year,
                "month": request.month,
                "employee_count": len(request.employee_ids),
            },
        }

    except ScheduleAppError:
        raise
    except Exception as e:
        traceback.print_exc()
        raise ScheduleAppError(
            "error",
            f"Erreur lors de l'application du modèle: {str(e)}",
            status_code=500,
        ) from e
