# app/modules/payroll/documents/payslip_generator.py
# Migré depuis services/payslip_generator.py. Comportement identique.
# Imports : app.core.*, payroll.analyzer, saisies_avances (queries + enrich_payslip), repos_compensateur.service.
# Génération in-process via app.modules.payroll.documents.payslip_run_heures (plus de subprocess).

import json
import logging
import sys
import traceback
import calendar
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.core.database import supabase
from app.core.paths import (
    payroll_engine_root,
    payroll_engine_employee_folder,
    payroll_engine_entreprise_json,
)
from app.modules.payroll.application.analyzer import (
    analyser_horaires_du_mois as payroll_analyzer_analyser,
)


def _parse_if_json_string(value: Any) -> Any:
    """Tente de parser une chaîne en JSON ; si ça échoue, retourne la valeur telle quelle."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def process_payslip_generation(employee_id: str, year: int, month: int):
    """
    Workflow de génération de paie "juste à temps", 100% basé sur la BDD,
    avec une gestion propre des fichiers temporaires.
    """
    files_to_cleanup = []
    dirs_to_cleanup = []
    try:
        # --- ÉTAPE 1 : RÉCUPÉRER TOUTES LES DONNÉES DEPUIS SUPABASE ---

        employee_data = supabase.table('employees').select("*").eq('id', employee_id).single().execute().data
        if not employee_data:
            raise HTTPException(status_code=404, detail="Employé non trouvé.")

        company_id = employee_data.get('company_id')
        if not company_id:
            raise HTTPException(status_code=400, detail=f"L'employé {employee_id} n'est pas associé à une entreprise (company_id manquant).")
        employee_folder_name = employee_data['employee_folder_name']

        company_data = supabase.table('companies').select("*").eq('id', company_id).single().execute().data
        if not company_data:
            raise HTTPException(status_code=404, detail=f"Données de l'entreprise (ID: {company_id}) non trouvées.")

        print("\n" + "="*25 + " DEBUG: Données de l'entreprise (BDD) " + "="*25, file=sys.stderr)
        print(json.dumps(company_data, indent=2, default=str), file=sys.stderr)
        print("="*80 + "\n", file=sys.stderr)

        duree_hebdo = employee_data.get('duree_hebdomadaire')
        if not duree_hebdo:
            raise HTTPException(status_code=400, detail="Durée hebdomadaire non définie.")

        dates_to_process = []
        for i in [-1, 0, 1]:
            d = date(year, month, 15)
            m_offset, y_offset = (d.month + i, d.year)
            if m_offset == 0:
                m_offset, y_offset = (12, y_offset - 1)
            elif m_offset == 13:
                m_offset, y_offset = (1, y_offset + 1)
            dates_to_process.append({'year': y_offset, 'month': m_offset})

        schedule_res = supabase.table('employee_schedules').select("year, month, planned_calendar, actual_hours") \
            .eq('employee_id', employee_id) \
            .in_('year', [d['year'] for d in dates_to_process]) \
            .in_('month', [d['month'] for d in dates_to_process]) \
            .execute()

        prev_month, prev_year = (month - 1, year) if month > 1 else (12, year - 1)
        cumuls_res = supabase.table('employee_schedules').select("cumuls").match({'employee_id': employee_id, 'year': prev_year, 'month': prev_month}).maybe_single().execute()
        saisies_res = supabase.table('monthly_inputs').select("*").match({'employee_id': employee_id, 'year': year, 'month': month}).execute()

        # --- ÉTAPE 2 : PRÉPARATION ET CALCUL EN MÉMOIRE ---

        db_data_map = {(row['year'], row['month']): row for row in schedule_res.data}
        planned_data_all_months, actual_data_all_months = [], []
        for date_info in dates_to_process:
            y, m = date_info['year'], date_info['month']
            db_row = db_data_map.get((y, m))
            planned_list = (db_row.get('planned_calendar') or {}).get('calendrier_prevu', []) if db_row else []
            actual_list = (db_row.get('actual_hours') or {}).get('calendrier_reel', []) if db_row else []
            for entry in planned_list:
                new_entry = entry.copy()
                new_entry.update({"annee": y, "mois": m})
                planned_data_all_months.append(new_entry)
            for entry in actual_list:
                new_entry = entry.copy()
                new_entry.update({"annee": y, "mois": m})
                actual_data_all_months.append(new_entry)

        payroll_events_list = payroll_analyzer_analyser(planned_data_all_months, actual_data_all_months, duree_hebdo, year, month, employee_folder_name)
        payroll_events_json = { "periode": {"annee": year, "mois": month}, "calendrier_analyse": payroll_events_list }
        print(f"\nDEBUG [Generator]: Nombre de saisies trouvées en BDD pour ce mois : {len(saisies_res.data)}\n")

        last_day = calendar.monthrange(year, month)[1]

        expense_reports_res = supabase.table('expense_reports') \
            .select("type, amount, date") \
            .match({'employee_id': employee_id, 'status': 'validated'}) \
            .gte('date', date(year, month, 1).isoformat()) \
            .lte('date', date(year, month, last_day).isoformat()) \
            .execute()

        saisies_data = { "periode": {"mois": month, "annee": year}, "primes": [] }
        for row in saisies_res.data:
            prime_entry = {
                "prime_id": row['name'].replace(" ", "_"),
                "montant": row['amount'],
                "soumise_a_cotisations": row.get('is_socially_taxed', True),
                "soumise_a_impot": row.get('is_taxable', True)
            }
            saisies_data["primes"].append(prime_entry)

        if expense_reports_res.data:
            print(f"DEBUG [Generator] - Ajout de {len(expense_reports_res.data)} note(s) de frais aux saisies.")
            for expense in expense_reports_res.data:
                expense_prime_id = f"remb_{expense['type'].lower().replace(' ', '_')}_{expense['date']}"
                expense_entry = {
                    "prime_id": expense_prime_id,
                    "montant": expense['amount'],
                    "soumise_a_cotisations": False,
                    "soumise_a_impot": False
                }
                saisies_data["primes"].append(expense_entry)
                print(f"DEBUG [Generator] - Note de frais ajoutée: {expense_entry}")

        try:
            from app.modules.saisies_avances.infrastructure.queries import (
                get_advances_to_repay,
            )
            from decimal import Decimal

            advances_to_repay = get_advances_to_repay(employee_id, year, month)
            total_advances_repayment = Decimal("0")

            print(f"[DEBUG GENERATOR] Avances à rembourser trouvées: {len(advances_to_repay)}")

            for advance in advances_to_repay:
                remaining = Decimal(str(advance.get('remaining_amount', 0)))
                if remaining <= 0:
                    continue

                if advance.get('repayment_mode') == 'single':
                    repayment_amount = remaining
                else:
                    approved_amount = Decimal(str(advance.get('approved_amount', 0)))
                    repayment_months = advance.get('repayment_months', 1)
                    repayment_amount = approved_amount / Decimal(str(repayment_months))
                    repayment_amount = min(repayment_amount, remaining)

                total_advances_repayment += repayment_amount
                print(f"[DEBUG GENERATOR] Avance {advance.get('id')}: {float(repayment_amount)}€ à rembourser ce mois")

            saisies_data['acompte'] = float(total_advances_repayment)
            print(f"[DEBUG GENERATOR] Total des remboursements d'avances à déduire: {float(total_advances_repayment)}€")
        except Exception as e:
            logging.warning(f"Erreur lors du calcul des avances à rembourser: {e}")
            print(f"[WARNING GENERATOR] Erreur calcul avances: {e}", file=sys.stderr)
            saisies_data['acompte'] = 0.0

        previous_cumuls_data = (cumuls_res.data or {}).get('cumuls') if cumuls_res else None
        if previous_cumuls_data is None:
            previous_cumuls_data = { "periode": {"annee_en_cours": year, "dernier_mois_calcule": 0}, "cumuls": { "brut_total": 0.0, "heures_remunerees": 0.0, "reduction_generale_patronale": 0.0, "net_imposable": 0.0, "impot_preleve_a_la_source": 0.0, "heures_supplementaires_remunerees": 0.0 } }

        # --- ÉTAPE 3 : ÉCRIRE LES FICHIERS TEMPORAIRES ET EXÉCUTER ---

        employee_path = payroll_engine_employee_folder(employee_folder_name)
        employee_path.mkdir(parents=True, exist_ok=True)
        sub_dirs = ["evenements_paie", "saisies", "cumuls", "bulletins", "calendriers", "horaires"]
        for sub_dir in sub_dirs:
            (employee_path / sub_dir).mkdir(parents=True, exist_ok=True)
            dirs_to_cleanup.append(employee_path / sub_dir)
        dirs_to_cleanup.append(employee_path)

        def write_temp_json(path: Path, data: dict):
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
            files_to_cleanup.append(path)

        contrat_json_content = {
            "salarie": {"nom": employee_data.get('last_name'),"prenom": employee_data.get('first_name'),"nir": employee_data.get('nir'),"date_naissance": employee_data.get('date_naissance'),"lieu_naissance": employee_data.get('lieu_naissance'),"nationalite": employee_data.get('nationalite'),"adresse": _parse_if_json_string(employee_data.get('adresse')),"coordonnees_bancaires": _parse_if_json_string(employee_data.get('coordonnees_bancaires')),},
            "contrat": {"date_entree": employee_data.get('hire_date'),"type_contrat": employee_data.get('contract_type'),"statut": employee_data.get('statut'),"emploi": employee_data.get('job_title'),"periode_essai": _parse_if_json_string(employee_data.get('periode_essai')),"temps_travail": {"is_temps_partiel": employee_data.get('is_temps_partiel'), "duree_hebdomadaire": employee_data.get('duree_hebdomadaire')}},
            "remuneration": {"salaire_de_base": _parse_if_json_string(employee_data.get('salaire_de_base')),"classification_conventionnelle": _parse_if_json_string(employee_data.get('classification_conventionnelle')),"elements_variables": _parse_if_json_string(employee_data.get('elements_variables')),"avantages_en_nature": _parse_if_json_string(employee_data.get('avantages_en_nature')),},
            "specificites_paie": _parse_if_json_string(employee_data.get('specificites_paie')) or {},
        }
        if not isinstance(contrat_json_content.get("contrat"), dict):
            raise HTTPException(status_code=400, detail="Données du contrat employé incomplètes. Vérifiez les données en base.")
        print("\n" + "="*30 + " DEBUG contrat.json " + "="*30, file=sys.stderr)
        try:
            specificites = contrat_json_content.get('specificites_paie')
            print(f"DEBUG [Generator]: Type de 'specificites_paie' après parsing: {type(specificites)}", file=sys.stderr)
            print(f"DEBUG [Generator]: Clé 'specificites_paie' (brut): {specificites}", file=sys.stderr)
            print("DEBUG [Generator]: Contenu FINAL qui sera écrit dans contrat.json:", file=sys.stderr)
            print(json.dumps(contrat_json_content, indent=2, ensure_ascii=False, default=str), file=sys.stderr)
        except Exception as e:
            print(f"DEBUG [Generator]: ERREUR LORS DU DEBUG PRINT: {e}", file=sys.stderr)
        print("="*80 + "\n", file=sys.stderr)
        write_temp_json(employee_path / "contrat.json", contrat_json_content)

        entreprise_json_path = payroll_engine_entreprise_json()
        entreprise_json_content = {
            "_commentaire": "Ce fichier est généré dynamiquement à chaque cycle de paie.",
            "entreprise": {
                "identification": {
                    "raison_sociale": company_data.get("raison_sociale") or company_data.get("company_name"),
                    "siren": company_data.get("siren"),
                    "nic": company_data.get("nic"),
                    "siret": company_data.get("siret"),
                    "naf_ape": company_data.get("naf_ape"),
                    "forme_juridique": company_data.get("legal_form"),
                    "adresse": {
                        "rue": company_data.get("adresse_rue"),
                        "code_postal": company_data.get("adresse_code_postal"),
                        "ville": company_data.get("adresse_ville")
                    }
                },
                "parametres_paie": {
                    "idcc": company_data.get("idcc"),
                    "effectif": company_data.get("effectif"),
                    "taux_specifiques": {
                        "taux_at_mp": company_data.get("taux_at_mp"),
                        "taux_versement_mobilite": company_data.get("taux_vm"),
                        "taux_fnal": company_data.get("taux_fnal")
                    }
                }
            }
        }
        print("\n" + "="*20 + " DEBUG: Contenu généré pour entreprise.json " + "="*20, file=sys.stderr)
        print(json.dumps(entreprise_json_content, indent=2, default=str), file=sys.stderr)
        print("="*80 + "\n", file=sys.stderr)

        write_temp_json(entreprise_json_path, entreprise_json_content)
        write_temp_json(employee_path / "calendriers" / f"{month:02d}.json", (db_data_map.get((year, month)) or {}).get('planned_calendar') or {})
        write_temp_json(employee_path / "horaires" / f"{month:02d}.json", (db_data_map.get((year, month)) or {}).get('actual_hours') or {})

        write_temp_json(employee_path / "evenements_paie" / f"{month:02d}.json", payroll_events_json)
        events_res_M_minus_1 = supabase.table('employee_schedules').select("payroll_events").match({'employee_id': employee_id, 'year': prev_year, 'month': prev_month}).maybe_single().execute()
        payroll_events_M_minus_1 = (events_res_M_minus_1.data or {}).get('payroll_events') if events_res_M_minus_1 else {}
        write_temp_json(employee_path / "evenements_paie" / f"{prev_month:02d}.json", payroll_events_M_minus_1)
        write_temp_json(employee_path / "saisies" / f"{month:02d}.json", saisies_data)
        write_temp_json(employee_path / "cumuls" / f"{prev_month:02d}.json", previous_cumuls_data)

        engine_root = payroll_engine_root()
        from app.modules.payroll.documents.payslip_run_heures import run_payslip_generation_heures
        payslip_json_data = run_payslip_generation_heures(employee_path, year, month, engine_root)

        new_cumuls_path = employee_path / "cumuls" / f"{month:02d}.json"
        new_cumuls_json = json.loads(new_cumuls_path.read_text(encoding="utf-8")) if new_cumuls_path.exists() else {}
        files_to_cleanup.append(new_cumuls_path)

        pdf_name = f"Bulletin_{employee_folder_name}_{month:02d}-{year}.pdf"
        local_pdf_path = employee_path / "bulletins" / pdf_name
        storage_path = f"{company_id}/{employee_id}/bulletins/{pdf_name}"
        files_to_cleanup.append(local_pdf_path)

        with open(local_pdf_path, 'rb') as f:
            supabase.storage.from_("payslips").upload(path=storage_path, file=f.read(), file_options={"x-upsert": "true"})

        signed_url_response = supabase.storage.from_("payslips").create_signed_url(storage_path, 3600, options={'download': True})
        pdf_url = signed_url_response['signedURL']

        payslip_upsert_result = supabase.table('payslips').upsert({
            "employee_id": employee_id, "month": month, "year": year, "name": pdf_name,
            "payslip_data": payslip_json_data, "pdf_storage_path": storage_path, "url": pdf_url, "company_id": company_id
        }).execute()

        payslip_id = None
        if payslip_upsert_result.data:
            payslip_id = payslip_upsert_result.data[0].get('id')

            try:
                from app.modules.saisies_avances.application.service import enrich_payslip
                enriched_data = enrich_payslip(
                    payslip_json_data.copy(),
                    employee_id,
                    year,
                    month,
                    payslip_id=payslip_id
                )

                supabase.table('payslips').update({
                    'payslip_data': enriched_data
                }).eq('id', payslip_id).execute()

                try:
                    from app.modules.payroll.documents.payslip_editor import regenerate_pdf_from_data
                    enriched_pdf_path = regenerate_pdf_from_data(
                        enriched_data,
                        employee_id,
                        employee_folder_name,
                        company_id,
                        month,
                        year
                    )

                    with open(enriched_pdf_path, 'rb') as f:
                        supabase.storage.from_("payslips").upload(
                            path=storage_path,
                            file=f.read(),
                            file_options={"x-upsert": "true"}
                        )

                    print(f"[INFO] PDF régénéré avec remboursements d'avances: {enriched_pdf_path}", file=sys.stderr)
                except Exception as pdf_err:
                    logging.warning(f"Erreur lors de la régénération du PDF avec données enrichies: {pdf_err}")
                    print(f"[WARNING] Régénération PDF échouée: {pdf_err}", file=sys.stderr)

            except Exception as enrich_err:
                logging.warning(f"Erreur lors de l'enrichissement avec saisies/avances: {enrich_err}")
                print(f"[WARNING] Enrichissement saisies/avances échoué: {enrich_err}", file=sys.stderr)
                traceback.print_exc()

        supabase.table('employee_schedules').update({"cumuls": new_cumuls_json, "payroll_events": payroll_events_json}).match({'employee_id': employee_id, 'year': year, 'month': month}).execute()

        try:
            from app.modules.repos_compensateur.application.service import (
                recalculer_credits_repos_employe,
            )
            recalculer_credits_repos_employe(employee_id, company_id, year)
        except Exception as cor_err:
            print(f"[WARNING] COR recalc après génération bulletin: {cor_err}", file=sys.stderr)

        return { "status": "success", "message": "Bulletin généré avec succès.", "download_url": pdf_url }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for path in files_to_cleanup:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                print(f"Erreur lors du nettoyage du fichier {path}: {e}", file=sys.stderr)
        for _ in range(2):
            for d in reversed(dirs_to_cleanup):
                try:
                    if d.exists() and d.is_dir() and not any(d.iterdir()):
                        d.rmdir()
                except Exception as e:
                    print(f"Erreur lors du nettoyage du dossier {d}: {e}", file=sys.stderr)
