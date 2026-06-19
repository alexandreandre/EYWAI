# app/modules/payroll/documents/payslip_generator.py
# Migré depuis services/payslip_generator.py. Comportement identique.
# Imports : app.core.*, payroll.analyzer, saisies_avances (queries + enrich_payslip), repos_compensateur.service.
# Génération in-process via app.modules.payroll.documents.payslip_run_heures (plus de subprocess).

import calendar
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.modules.collective_agreements.application.idcc_resolution import (
    build_convention_collective_payload,
)
from app.core.database import supabase
from app.core.logging import get_logger, log_payroll_debug
from app.core.paths import (
    payroll_engine_root,
    payroll_engine_employee_folder,
)
from app.modules.jei_settings.application.queries import get_jei_settings_raw
from app.modules.payroll.application.analyzer import (
    analyser_horaires_du_mois as payroll_analyzer_analyser,
)
from app.modules.payroll.application.salary_evolution_payroll import (
    prepare_salary_evolution_for_payslip,
)

logger = get_logger("modules.payroll.documents.payslip_generator")


def _parse_if_json_string(value: Any) -> Any:
    """Tente de parser une chaîne en JSON ; si ça échoue, retourne la valeur telle quelle."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def resolve_date_sortie(employee_data: dict) -> Any:
    """Date de sortie effective d'un employé pour le bulletin.

    Priorité : sortie effective (employee_exits.last_working_day du dossier de
    sortie en cours) puis fin de contrat planifiée (employees.contract_end_date).
    Tolérant aux erreurs réseau (retourne contract_end_date en repli).
    """
    contract_end = employee_data.get("contract_end_date")
    exit_id = employee_data.get("current_exit_id")
    if not exit_id:
        return contract_end
    try:
        exit_res = (
            supabase.table("employee_exits")
            .select("last_working_day, status")
            .eq("id", exit_id)
            .maybe_single()
            .execute()
        )
        exit_row = exit_res.data if exit_res else None
        if exit_row and (exit_row.get("status") or "").lower() not in (
            "cancelled",
            "canceled",
            "annule",
            "annulee",
        ):
            return exit_row.get("last_working_day") or contract_end
    except Exception as exc:  # pragma: no cover - réseau best-effort
        logger.warning(f"[Generator] Lecture employee_exits échouée: {exc}")
    return contract_end


def process_payslip_generation(
    employee_id: str,
    year: int,
    month: int,
    *,
    ijss_brut_override: float | None = None,
    ijss_tracking_meta: dict | None = None,
):
    """
    Workflow de génération de paie "juste à temps", 100% basé sur la BDD,
    avec une gestion propre des fichiers temporaires.
    """
    files_to_cleanup = []
    dirs_to_cleanup = []
    try:
        # --- ÉTAPE 1 : RÉCUPÉRER TOUTES LES DONNÉES DEPUIS SUPABASE ---

        employee_data = (
            supabase.table("employees")
            .select("*")
            .eq("id", employee_id)
            .single()
            .execute()
            .data
        )
        if not employee_data:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")

        company_id = employee_data.get("company_id")
        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="Ce collaborateur n'est rattaché à aucune entreprise. Complétez sa fiche employé.",
            )
        employee_folder_name = employee_data["employee_folder_name"]

        company_data = (
            supabase.table("companies")
            .select("*")
            .eq("id", company_id)
            .single()
            .execute()
            .data
        )
        if not company_data:
            raise HTTPException(
                status_code=404,
                detail="Les informations de l'entreprise sont introuvables. Contactez le support.",
            )

        log_payroll_debug(logger, '\n' + '=' * 25 + " DEBUG: Données de l'entreprise (BDD) " + '=' * 25)
        log_payroll_debug(logger, json.dumps(company_data, indent=2, default=str))
        log_payroll_debug(logger, '=' * 80 + '\n')

        duree_hebdo = employee_data.get("duree_hebdomadaire")
        if not duree_hebdo:
            raise HTTPException(
                status_code=400,
                detail="La durée hebdomadaire n'est pas renseignée sur la fiche du collaborateur.",
            )

        dates_to_process = []
        for i in [-1, 0, 1]:
            d = date(year, month, 15)
            m_offset, y_offset = (d.month + i, d.year)
            if m_offset == 0:
                m_offset, y_offset = (12, y_offset - 1)
            elif m_offset == 13:
                m_offset, y_offset = (1, y_offset + 1)
            dates_to_process.append({"year": y_offset, "month": m_offset})

        schedule_res = (
            supabase.table("employee_schedules")
            .select("year, month, planned_calendar, actual_hours")
            .eq("employee_id", employee_id)
            .in_("year", [d["year"] for d in dates_to_process])
            .in_("month", [d["month"] for d in dates_to_process])
            .execute()
        )

        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        cumuls_res = (
            supabase.table("employee_schedules")
            .select("cumuls")
            .match({"employee_id": employee_id, "year": prev_year, "month": prev_month})
            .maybe_single()
            .execute()
        )
        saisies_res = (
            supabase.table("monthly_inputs")
            .select("*")
            .match({"employee_id": employee_id, "year": year, "month": month})
            .execute()
        )

        # --- ÉTAPE 2 : PRÉPARATION ET CALCUL EN MÉMOIRE ---

        db_data_map = {(row["year"], row["month"]): row for row in schedule_res.data}
        planned_data_all_months, actual_data_all_months = [], []
        for date_info in dates_to_process:
            y, m = date_info["year"], date_info["month"]
            db_row = db_data_map.get((y, m))
            planned_list = (
                (db_row.get("planned_calendar") or {}).get("calendrier_prevu", [])
                if db_row
                else []
            )
            actual_list = (
                (db_row.get("actual_hours") or {}).get("calendrier_reel", [])
                if db_row
                else []
            )
            for entry in planned_list:
                new_entry = entry.copy()
                new_entry.update({"annee": y, "mois": m})
                planned_data_all_months.append(new_entry)
            for entry in actual_list:
                new_entry = entry.copy()
                new_entry.update({"annee": y, "mois": m})
                actual_data_all_months.append(new_entry)

        payroll_events_list = payroll_analyzer_analyser(
            planned_data_all_months,
            actual_data_all_months,
            duree_hebdo,
            year,
            month,
            employee_folder_name,
        )
        payroll_events_json = {
            "periode": {"annee": year, "mois": month},
            "calendrier_analyse": payroll_events_list,
        }
        # M-1 : recalcul (pas le cache BDD) pour la portion de période chevauchante.
        payroll_events_prev_list = payroll_analyzer_analyser(
            planned_data_all_months,
            actual_data_all_months,
            duree_hebdo,
            prev_year,
            prev_month,
            employee_folder_name,
        )
        payroll_events_M_minus_1 = {
            "periode": {"annee": prev_year, "mois": prev_month},
            "calendrier_analyse": payroll_events_prev_list,
        }
        log_payroll_debug(logger, f'\nDEBUG [Generator]: Nombre de saisies trouvées en BDD pour ce mois : {len(saisies_res.data)}\n')

        last_day = calendar.monthrange(year, month)[1]

        expense_reports_res = (
            supabase.table("expense_reports")
            .select("type, amount, date")
            .match({"employee_id": employee_id, "status": "validated"})
            .gte("date", date(year, month, 1).isoformat())
            .lte("date", date(year, month, last_day).isoformat())
            .execute()
        )

        saisies_data = {"periode": {"mois": month, "annee": year}, "primes": []}
        if ijss_brut_override is not None:
            saisies_data["ijss_brut_override"] = float(ijss_brut_override)
        for row in saisies_res.data:
            prime_entry = {
                "prime_id": row["name"].replace(" ", "_"),
                "montant": row["amount"],
                "soumise_a_cotisations": row.get("is_socially_taxed", True),
                "soumise_a_impot": row.get("is_taxable", True),
            }
            saisies_data["primes"].append(prime_entry)

        if expense_reports_res.data:
            log_payroll_debug(logger, f'DEBUG [Generator] - Ajout de {len(expense_reports_res.data)} note(s) de frais aux saisies.')
            for expense in expense_reports_res.data:
                expense_prime_id = f"remb_{expense['type'].lower().replace(' ', '_')}_{expense['date']}"
                expense_entry = {
                    "prime_id": expense_prime_id,
                    "montant": expense["amount"],
                    "soumise_a_cotisations": False,
                    "soumise_a_impot": False,
                }
                if expense.get("vat_rate") is not None:
                    expense_entry["vat_rate"] = expense["vat_rate"]
                if expense.get("amount_ht") is not None:
                    expense_entry["amount_ht"] = expense["amount_ht"]
                if expense.get("vat_amount") is not None:
                    expense_entry["vat_amount"] = expense["vat_amount"]
                saisies_data["primes"].append(expense_entry)
                log_payroll_debug(logger, f'DEBUG [Generator] - Note de frais ajoutée: {expense_entry}')

        try:
            from app.modules.saisies_avances.infrastructure.queries import (
                get_advances_to_repay,
            )
            from decimal import Decimal

            advances_to_repay = get_advances_to_repay(employee_id, year, month)
            total_advances_repayment = Decimal("0")

            log_payroll_debug(logger, f'[DEBUG GENERATOR] Avances à rembourser trouvées: {len(advances_to_repay)}')

            for advance in advances_to_repay:
                remaining = Decimal(str(advance.get("remaining_amount", 0)))
                if remaining <= 0:
                    continue

                if advance.get("repayment_mode") == "single":
                    repayment_amount = remaining
                else:
                    approved_amount = Decimal(str(advance.get("approved_amount", 0)))
                    repayment_months = advance.get("repayment_months", 1)
                    repayment_amount = approved_amount / Decimal(str(repayment_months))
                    repayment_amount = min(repayment_amount, remaining)

                total_advances_repayment += repayment_amount
                log_payroll_debug(logger, f"[DEBUG GENERATOR] Avance {advance.get('id')}: {float(repayment_amount)}€ à rembourser ce mois")

            saisies_data["acompte"] = float(total_advances_repayment)
            log_payroll_debug(logger, f"[DEBUG GENERATOR] Total des remboursements d'avances à déduire: {float(total_advances_repayment)}€")
        except Exception as e:
            logging.warning(f"Erreur lors du calcul des avances à rembourser: {e}")
            logger.warning(f'[WARNING GENERATOR] Erreur calcul avances: {e}')
            saisies_data["acompte"] = 0.0

        previous_cumuls_data = (
            (cumuls_res.data or {}).get("cumuls") if cumuls_res else None
        )
        if previous_cumuls_data is None:
            previous_cumuls_data = {
                "periode": {"annee_en_cours": year, "dernier_mois_calcule": 0},
                "cumuls": {
                    "brut_total": 0.0,
                    "heures_remunerees": 0.0,
                    "reduction_generale_patronale": 0.0,
                    "net_imposable": 0.0,
                    "impot_preleve_a_la_source": 0.0,
                    "heures_supplementaires_remunerees": 0.0,
                },
            }

        # --- ÉTAPE 3 : ÉCRIRE LES FICHIERS TEMPORAIRES ET EXÉCUTER ---

        employee_path = payroll_engine_employee_folder(employee_folder_name)
        employee_path.mkdir(parents=True, exist_ok=True)
        sub_dirs = [
            "evenements_paie",
            "saisies",
            "cumuls",
            "bulletins",
            "calendriers",
            "horaires",
        ]
        for sub_dir in sub_dirs:
            (employee_path / sub_dir).mkdir(parents=True, exist_ok=True)
            dirs_to_cleanup.append(employee_path / sub_dir)
        dirs_to_cleanup.append(employee_path)

        def write_temp_json(path: Path, data: dict):
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            files_to_cleanup.append(path)

        contrat_json_content = {
            "employee_id": employee_id,
            "salarie": {
                "nom": employee_data.get("last_name"),
                "prenom": employee_data.get("first_name"),
                "nir": employee_data.get("nir"),
                "date_naissance": employee_data.get("date_naissance"),
                "lieu_naissance": employee_data.get("lieu_naissance"),
                "nationalite": employee_data.get("nationalite"),
                "adresse": _parse_if_json_string(employee_data.get("adresse")),
                "coordonnees_bancaires": _parse_if_json_string(
                    employee_data.get("coordonnees_bancaires")
                ),
            },
            "contrat": {
                "date_entree": employee_data.get("hire_date"),
                "type_contrat": employee_data.get("contract_type"),
                "date_conclusion_contrat": employee_data.get(
                    "date_conclusion_contrat"
                ),
                "date_debut_execution": employee_data.get("date_debut_execution"),
                "date_fin_contrat": employee_data.get("contract_end_date"),
                "date_sortie": resolve_date_sortie(employee_data),
                "statut": employee_data.get("statut"),
                "emploi": employee_data.get("job_title"),
                "periode_essai": _parse_if_json_string(
                    employee_data.get("periode_essai")
                ),
                "temps_travail": {
                    "is_temps_partiel": employee_data.get("is_temps_partiel"),
                    "duree_hebdomadaire": employee_data.get("duree_hebdomadaire"),
                },
            },
            "remuneration": {
                "salaire_de_base": _parse_if_json_string(
                    employee_data.get("salaire_de_base")
                ),
                "classification_conventionnelle": _parse_if_json_string(
                    employee_data.get("classification_conventionnelle")
                ),
                "convention_collective": build_convention_collective_payload(
                    employee_data, company_data
                ),
                "elements_variables": _parse_if_json_string(
                    employee_data.get("elements_variables")
                ),
                "avantages_en_nature": _parse_if_json_string(
                    employee_data.get("avantages_en_nature")
                ),
            },
            "specificites_paie": _parse_if_json_string(
                employee_data.get("specificites_paie")
            )
            or {},
        }
        if not isinstance(contrat_json_content.get("contrat"), dict):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Les données contractuelles du collaborateur sont incomplètes. "
                    "Complétez sa fiche employé (contrat, rémunération, temps de travail)."
                ),
            )
        log_payroll_debug(logger, '\n' + '=' * 30 + ' DEBUG contrat.json ' + '=' * 30)
        try:
            specificites = contrat_json_content.get("specificites_paie")
            log_payroll_debug(logger, f"DEBUG [Generator]: Type de 'specificites_paie' après parsing: {type(specificites)}")
            log_payroll_debug(logger, f"DEBUG [Generator]: Clé 'specificites_paie' (brut): {specificites}")
            log_payroll_debug(logger, 'DEBUG [Generator]: Contenu FINAL qui sera écrit dans contrat.json:')
            log_payroll_debug(logger, json.dumps(contrat_json_content, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            logger.warning(f'DEBUG [Generator]: ERREUR LORS DU DEBUG PRINT: {e}')
        log_payroll_debug(logger, '=' * 80 + '\n')

        from app.modules.employee_loans.application.payroll_integration import (
            inject_loan_benefit_in_kind,
        )

        contrat_json_content = inject_loan_benefit_in_kind(
            contrat_json_content, employee_id, year, month
        )

        try:
            salary_evo = prepare_salary_evolution_for_payslip(
                employee_id, str(company_id), year, month
            )
            if salary_evo:
                remuneration = contrat_json_content.setdefault("remuneration", {})
                if salary_evo.get("salaire_de_base"):
                    remuneration["salaire_de_base"] = salary_evo["salaire_de_base"]
                if salary_evo.get("evolution_salaire_mois"):
                    remuneration["evolution_salaire_mois"] = salary_evo[
                        "evolution_salaire_mois"
                    ]
        except Exception as evo_err:
            logger.warning(f"Erreur résolution évolution salaire: {evo_err}")

        write_temp_json(employee_path / "contrat.json", contrat_json_content)

        # Isolation par génération : écrit dans le dossier de l'employé plutôt que
        # dans le fichier partagé data/entreprise.json (concurrence multi-tenant).
        jei_settings = get_jei_settings_raw(str(company_id))
        from app.modules.prime_anciennete_settings.application.queries import (
            get_prime_anciennete_overrides_for_payslip,
        )

        prime_anciennete_overrides = get_prime_anciennete_overrides_for_payslip(
            str(company_id)
        )
        jei_bloc = {
            "enabled": jei_settings.jei_enabled,
            "date_creation_etablissement": (
                jei_settings.date_creation_etablissement.isoformat()
                if jei_settings.date_creation_etablissement
                else None
            ),
            "taux_exoneration": jei_settings.taux_exoneration,
        }

        entreprise_json_path = employee_path / "entreprise.json"
        entreprise_json_content = {
            "_commentaire": "Ce fichier est généré dynamiquement à chaque cycle de paie.",
            "entreprise": {
                "identification": {
                    "raison_sociale": company_data.get("raison_sociale")
                    or company_data.get("company_name"),
                    "siren": company_data.get("siren"),
                    "nic": company_data.get("nic"),
                    "siret": company_data.get("siret"),
                    "naf_ape": company_data.get("naf_ape"),
                    "forme_juridique": company_data.get("legal_form"),
                    "adresse": {
                        "rue": company_data.get("adresse_rue"),
                        "code_postal": company_data.get("adresse_code_postal"),
                        "ville": company_data.get("adresse_ville"),
                    },
                },
                "parametres_paie": {
                    "idcc": company_data.get("idcc"),
                    "effectif": company_data.get("effectif"),
                    "taux_specifiques": {
                        "taux_at_mp": company_data.get("taux_at_mp"),
                        "taux_versement_mobilite": company_data.get("taux_vm"),
                        "taux_fnal": company_data.get("taux_fnal"),
                    },
                    "jei": jei_bloc,
                    "prime_anciennete": prime_anciennete_overrides or None,
                },
            },
        }
        logger.info('\n' + '=' * 20 + ' DEBUG: Contenu généré pour entreprise.json ' + '=' * 20)
        log_payroll_debug(logger, json.dumps(entreprise_json_content, indent=2, default=str))
        log_payroll_debug(logger, '=' * 80 + '\n')

        write_temp_json(entreprise_json_path, entreprise_json_content)
        write_temp_json(
            employee_path / "calendriers" / f"{month:02d}.json",
            (db_data_map.get((year, month)) or {}).get("planned_calendar") or {},
        )
        write_temp_json(
            employee_path / "horaires" / f"{month:02d}.json",
            (db_data_map.get((year, month)) or {}).get("actual_hours") or {},
        )

        write_temp_json(
            employee_path / "evenements_paie" / f"{month:02d}.json", payroll_events_json
        )
        write_temp_json(
            employee_path / "evenements_paie" / f"{prev_month:02d}.json",
            payroll_events_M_minus_1,
        )
        write_temp_json(employee_path / "saisies" / f"{month:02d}.json", saisies_data)
        write_temp_json(
            employee_path / "cumuls" / f"{prev_month:02d}.json", previous_cumuls_data
        )

        engine_root = payroll_engine_root()
        from app.modules.payroll.documents.payslip_run_heures import (
            run_payslip_generation_heures,
        )

        payslip_json_data = run_payslip_generation_heures(
            employee_path,
            year,
            month,
            engine_root,
            company_id=str(company_id),
            employee_id=str(employee_id),
        )

        from app.modules.modulation.application.payroll_hook import (
            ModulationPayrollResult,
            enrich_payroll_events_metadata,
        )

        mod_block = payslip_json_data.get("modulation_account") if isinstance(
            payslip_json_data, dict
        ) else None
        mod_result = None
        if mod_block:
            mod_result = ModulationPayrollResult(
                hs_realisees=float(mod_block.get("hs_realisees") or 0),
                hs_credited=float(mod_block.get("hs_credited") or 0),
                hs_paid=float(mod_block.get("hs_paid") or 0),
            )
        payroll_events_json = enrich_payroll_events_metadata(
            payroll_events_json,
            payroll_events_list,
            mod_result,
        )

        if ijss_tracking_meta:
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["ijss_tracking"] = ijss_tracking_meta

        new_cumuls_path = employee_path / "cumuls" / f"{month:02d}.json"
        new_cumuls_json = (
            json.loads(new_cumuls_path.read_text(encoding="utf-8"))
            if new_cumuls_path.exists()
            else {}
        )
        files_to_cleanup.append(new_cumuls_path)

        pdf_name = f"Bulletin_{employee_folder_name}_{month:02d}-{year}.pdf"
        local_pdf_path = employee_path / "bulletins" / pdf_name
        storage_path = f"{company_id}/{employee_id}/bulletins/{pdf_name}"
        files_to_cleanup.append(local_pdf_path)

        with open(local_pdf_path, "rb") as f:
            supabase.storage.from_("payslips").upload(
                path=storage_path, file=f.read(), file_options={"x-upsert": "true"}
            )

        signed_url_response = supabase.storage.from_("payslips").create_signed_url(
            storage_path, 3600, options={"download": True}
        )
        pdf_url = signed_url_response["signedURL"]

        payslip_upsert_result = (
            supabase.table("payslips")
            .upsert(
                {
                    "employee_id": employee_id,
                    "month": month,
                    "year": year,
                    "name": pdf_name,
                    "payslip_data": payslip_json_data,
                    "pdf_storage_path": storage_path,
                    "url": pdf_url,
                    "company_id": company_id,
                },
                on_conflict="company_id,employee_id,year,month",
            )
            .execute()
        )

        payslip_id = None
        final_payslip_data = payslip_json_data
        if payslip_upsert_result.data:
            payslip_id = payslip_upsert_result.data[0].get("id")

            from app.modules.employee_loans.application.payroll_integration import (
                PdfRegenConfig,
                enrich_payslip_after_upsert,
            )

            final_payslip_data = enrich_payslip_after_upsert(
                payslip_json_data,
                employee_id,
                year,
                month,
                payslip_id,
                pdf_regen=PdfRegenConfig(
                    employee_id=employee_id,
                    employee_folder_name=employee_folder_name,
                    company_id=str(company_id),
                    month=month,
                    year=year,
                    storage_path=storage_path,
                ),
            )

        supabase.table("employee_schedules").update(
            {"cumuls": new_cumuls_json, "payroll_events": payroll_events_json}
        ).match({"employee_id": employee_id, "year": year, "month": month}).execute()

        try:
            from app.modules.repos_compensateur.application.service import (
                recalculer_credits_repos_employe,
            )

            recalculer_credits_repos_employe(employee_id, company_id, year)
        except Exception as cor_err:
            logger.warning(f'[WARNING] COR recalc après génération bulletin: {cor_err}')

        from app.modules.payroll.engine.controles_convention import (
            extraire_messages_alertes_rh,
        )

        rh_warnings = extraire_messages_alertes_rh(final_payslip_data)

        return {
            "status": "success",
            "message": "Bulletin généré avec succès.",
            "download_url": pdf_url,
            "payslip_id": payslip_id,
            "warnings": rh_warnings,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Exception")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for path in files_to_cleanup:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.warning(f'Erreur lors du nettoyage du fichier {path}: {e}')
        for _ in range(2):
            for d in reversed(dirs_to_cleanup):
                try:
                    if d.exists() and d.is_dir() and not any(d.iterdir()):
                        d.rmdir()
                except Exception as e:
                    logger.warning(f'Erreur lors du nettoyage du dossier {d}: {e}')
