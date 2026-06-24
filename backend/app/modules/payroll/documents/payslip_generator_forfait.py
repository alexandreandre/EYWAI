# app/modules/payroll/documents/payslip_generator_forfait.py
# Migré depuis services/payslip_generator_forfait.py. Comportement identique.
# Avances : app.modules.saisies_avances.infrastructure.queries.get_advances_to_repay.
# Génération in-process via app.modules.payroll.documents.payslip_run_forfait (plus de subprocess).

"""
Service de génération de paie adapté au forfait jour.

Ce service détecte automatiquement si un employé est en forfait jour
et utilise le générateur approprié.
"""

from app.core.logging import get_logger

logger = get_logger("modules.payroll.documents.payslip_generator_forfait")

import json
import logging
import traceback
import calendar
from datetime import date
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

from app.core.database import supabase
from app.modules.collective_agreements.application.idcc_resolution import (
    build_convention_collective_payload,
)
from app.modules.jei_settings.application.queries import get_jei_settings_raw
from app.core.paths import (
    payroll_engine_root,
    payroll_engine_employee_folder,
)


from app.shared.domain.employment_rules import is_forfait_jour as is_forfait_jour
from app.modules.payroll.documents.payslip_generator import resolve_date_sortie


def process_payslip_generation_forfait(
    employee_id: str,
    year: int,
    month: int,
    *,
    ijss_brut_override: float | None = None,
    ijss_tracking_meta: dict | None = None,
):
    """
    Génère une fiche de paie pour un employé en forfait jour.

    Cette fonction est similaire à process_payslip_generation mais utilise
    les modules spécifiques au forfait jour.
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
        statut = employee_data.get("statut")

        if not is_forfait_jour(statut):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Ce collaborateur n'est pas en forfait jour. "
                    "Utilisez la génération standard ou corrigez son statut."
                ),
            )

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

        duree_hebdo = employee_data.get("duree_hebdomadaire") or 35.0

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

        # --- ÉTAPE 2 : PRÉPARATION DES DONNÉES ---
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

        try:
            from app.modules.saisies_avances.infrastructure.queries import (
                get_advances_to_repay,
            )
            from decimal import Decimal

            advances_to_repay = get_advances_to_repay(employee_id, year, month)
            total_advances_repayment = Decimal("0")

            for advance in advances_to_repay:
                remaining = Decimal(str(advance.get("remaining_amount", 0)))
                if remaining <= 0:
                    continue

                monthly_repayment = Decimal(
                    str(advance.get("monthly_repayment_amount", 0))
                )
                repayment_this_month = min(remaining, monthly_repayment)
                total_advances_repayment += repayment_this_month

            if total_advances_repayment > 0:
                advance_entry = {
                    "prime_id": "remboursement_avance_salaire",
                    "montant": -float(total_advances_repayment),
                    "soumise_a_cotisations": False,
                    "soumise_a_impot": False,
                }
                saisies_data["primes"].append(advance_entry)
        except Exception as e:
            logging.warning(
                "Erreur lors du calcul des avances à rembourser (forfait): %s", e
            )

        # --- ÉTAPE 3 : PRÉPARATION DES FICHIERS TEMPORAIRES ---
        employee_path = payroll_engine_employee_folder(employee_folder_name)
        employee_path.mkdir(parents=True, exist_ok=True)
        sub_dirs = [
            "calendriers",
            "horaires",
            "evenements_paie",
            "saisies",
            "cumuls",
            "bulletins",
        ]
        for sub_dir in sub_dirs:
            (employee_path / sub_dir).mkdir(parents=True, exist_ok=True)
            dirs_to_cleanup.append(employee_path / sub_dir)
        dirs_to_cleanup.append(employee_path)

        def write_temp_json(file_path: Path, content: Dict[str, Any]):
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, ensure_ascii=False, default=str)
            files_to_cleanup.append(file_path)

        salaire_base_raw = employee_data.get("salaire_de_base") or {}
        salaire_base_valeur = (
            salaire_base_raw.get("valeur", 0.0)
            if isinstance(salaire_base_raw, dict)
            else 0.0
        )

        contrat_json_content = {
            "employee_id": employee_id,
            "salarie": {
                "nom": employee_data.get("last_name"),
                "prenom": employee_data.get("first_name"),
                "nir": employee_data.get("nir"),
                "date_naissance": employee_data.get("date_naissance"),
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
                "statut": statut,
                "temps_travail": {"duree_hebdomadaire": duree_hebdo},
            },
            "remuneration": {
                "salaire_de_base": {"valeur": salaire_base_valeur},
                "classification_conventionnelle": employee_data.get(
                    "classification_conventionnelle", {}
                ),
                "convention_collective": build_convention_collective_payload(
                    employee_data, company_data
                ),
                "avantages_en_nature": employee_data.get("avantages_en_nature") or {},
            },
            "specificites_paie": employee_data.get("specificites_paie", {}),
            "saisie_du_mois": saisies_data,
        }

        try:
            from app.modules.payroll.application.salary_evolution_payroll import (
                prepare_salary_evolution_for_payslip,
            )

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
            logger.warning(f"Erreur résolution évolution salaire (forfait): {evo_err}")

        from app.modules.employee_loans.application.payroll_integration import (
            inject_loan_benefit_in_kind,
        )

        contrat_json_content = inject_loan_benefit_in_kind(
            contrat_json_content, employee_id, year, month
        )

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

        write_temp_json(entreprise_json_path, entreprise_json_content)

        for date_info in dates_to_process:
            y, m = date_info["year"], date_info["month"]
            db_row = db_data_map.get((y, m))

            planned_calendar_data = (
                (db_row.get("planned_calendar") or {}) if db_row else {}
            )
            write_temp_json(
                employee_path / "calendriers" / f"{m:02d}.json", planned_calendar_data
            )

            actual_hours_data = (db_row.get("actual_hours") or {}) if db_row else {}
            write_temp_json(
                employee_path / "horaires" / f"{m:02d}.json", actual_hours_data
            )

        if cumuls_res and cumuls_res.data and cumuls_res.data.get("cumuls"):
            previous_cumuls_data = cumuls_res.data.get("cumuls", {})
            if not isinstance(previous_cumuls_data, dict):
                previous_cumuls_data = {}
        else:
            previous_cumuls_data = {}

        cumuls_structure = {
            "cumuls": previous_cumuls_data
            if isinstance(previous_cumuls_data, dict)
            else {},
            "periode": {},
        }

        write_temp_json(
            employee_path / "cumuls" / f"{prev_month:02d}.json", cumuls_structure
        )

        write_temp_json(employee_path / "saisies" / f"{month:02d}.json", saisies_data)

        # --- ÉTAPE 4 : GÉNÉRATION IN-PROCESS (app uniquement) ---
        engine_root = payroll_engine_root()
        from app.modules.payroll.documents.payslip_run_forfait import (
            run_payslip_generation_forfait,
        )

        payslip_json_data = run_payslip_generation_forfait(
            employee_path,
            year,
            month,
            engine_root,
            company_id=str(company_id),
            employee_id=str(employee_id),
        )

        if ijss_tracking_meta:
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["ijss_tracking"] = ijss_tracking_meta

        # --- ÉTAPE 5 : SAUVEGARDER ---

        new_cumuls_path = employee_path / "cumuls" / f"{month:02d}.json"
        new_cumuls_json = (
            json.loads(new_cumuls_path.read_text(encoding="utf-8"))
            if new_cumuls_path.exists()
            else {}
        )
        files_to_cleanup.append(new_cumuls_path)

        pdf_name = f"Bulletin_{employee_folder_name}_{month:02d}-{year}_FORFAIT.pdf"
        local_pdf_path = employee_path / "bulletins" / pdf_name
        storage_path = f"{company_id}/{employee_id}/bulletins/{pdf_name}"
        files_to_cleanup.append(local_pdf_path)

        if local_pdf_path.exists():
            with open(local_pdf_path, "rb") as f:
                supabase.storage.from_("payslips").upload(
                    path=storage_path, file=f.read(), file_options={"x-upsert": "true"}
                )

        signed_url_response = supabase.storage.from_("payslips").create_signed_url(
            storage_path, 3600, options={"download": True}
        )
        pdf_url = signed_url_response["signedURL"]

        upsert_result = supabase.table("payslips").upsert(
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "year": year,
                "month": month,
                "name": pdf_name,
                "payslip_data": payslip_json_data,
                "pdf_storage_path": storage_path,
                "url": pdf_url,
            },
            on_conflict="company_id,employee_id,year,month",
        ).execute()

        payslip_id = None
        final_payslip_data = payslip_json_data
        if upsert_result.data:
            payslip_id = upsert_result.data[0].get("id")

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
                    pdf_name_suffix="_FORFAIT",
                ),
            )

        supabase.table("employee_schedules").update({"cumuls": new_cumuls_json}).match(
            {"employee_id": employee_id, "year": year, "month": month}
        ).execute()

        from app.modules.payroll.engine.controles_convention import (
            extraire_messages_alertes_rh,
        )

        rh_warnings = extraire_messages_alertes_rh(final_payslip_data)

        return {
            "status": "success",
            "message": "Bulletin forfait jour généré avec succès.",
            "download_url": pdf_url,
            "payslip_id": payslip_id,
            "warnings": rh_warnings,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logging.error(f"Erreur lors de la génération de paie forfait jour: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        for file_path in files_to_cleanup:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logging.warning(f"Impossible de supprimer {file_path}: {e}")
        for _ in range(2):
            for d in reversed(dirs_to_cleanup):
                try:
                    if d.exists() and d.is_dir() and not any(d.iterdir()):
                        d.rmdir()
                except Exception as e:
                    logging.warning(f"Impossible de supprimer le dossier {d}: {e}")
