# app/modules/payroll/documents/payslip_generator_forfait.py
# Migré depuis services/payslip_generator_forfait.py. Comportement identique.
# Avances : app.modules.saisies_avances.infrastructure.queries.get_advances_to_repay.
# Génération in-process via app.modules.payroll.documents.payslip_run_forfait (plus de subprocess).

"""
Service de génération de paie adapté au forfait jour.

Ce service détecte automatiquement si un employé est en forfait jour
et utilise le générateur approprié.
"""

from app.modules.payroll.application import arrets_reportes
from app.modules.payroll.documents.alertes_d_entree import alertes_d_entree_courantes
from app.shared.domain.effectif_seuils import (
    alerte_effectif,
    alerte_franchissement_seuil,
    effectif_retenu,
)
from app.core.logging import get_logger

logger = get_logger("modules.payroll.documents.payslip_generator_forfait")

import json
import logging
import calendar
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

from app.shared.reprise_paie import (
    CLE_DEPART_A_ZERO,
    RepriseNonPosee,
    alerte_depart_a_zero,
    detail_du_refus,
    raison_de_cumul_manquant,
)
from app.modules.payroll.domain.report_nap_negatif import (
    CLE_BULLETIN as CLE_REPORTS_NAP_NEGATIF,
)
from app.modules.payroll.engine.lectures import LectureIndispensable
from app.modules.payroll.engine.frais_professionnels import (
    entree_de_note_de_frais,
    notes_de_frais_dans_le_mns,
)
from app.modules.payroll.engine.replis import (
    fermer_collecte,
    fusionner_replis,
    ouvrir_collecte,
)
from app.modules.payroll.documents.dossier_de_travail import (
    nouveau_dossier_de_travail,
    supprimer_dossier_de_travail,
)
from app.modules.payroll.documents.bac_a_sable import (
    BacASable,
    cumuls_de_depart,
    saisies_du_mois,
)
from app.modules.payroll.documents.pdf_du_bulletin import (
    PdfNonImprime,
    exiger_le_pdf_imprime,
    chemin_enregistre,
    chemin_horodate,
    retirer_pdf_remplace,
)

from app.core.constants import MESSAGE_ERREUR_GENERATION
from app.core.database import supabase
from app.modules.payroll.engine.reference_remuneration import base_precarite_du_bulletin
from app.modules.collective_agreements.application.idcc_resolution import (
    build_convention_collective_payload,
)
from app.modules.collective_agreements.domain.convention_datee import fin_du_mois
from app.modules.jei_settings.application.queries import get_jei_settings_raw
from app.modules.payroll.application.monthly_specificites import (
    resolve_monthly_specificites,
)
from app.modules.collective_agreements.domain.classification import (
    normalize_classification_for_payroll,
)
from app.core.paths import (
    payroll_engine_root,
)


from app.shared.domain.employment_rules import (
    cumuls_precedents_du_contrat,
    is_forfait_jour as is_forfait_jour,
    payslip_employment_period_block_reason,
)
from app.modules.employees.application.contrat_du_mois import fiche_du_mois
from app.modules.payroll.documents.bulletin_par_contrat import (
    suffixe_du_pdf,
    variables_du_bulletin,
)
from app.shared.cle_du_bulletin import CONFLIT_BULLETIN
from app.modules.payroll.documents.payslip_generator import (
    resolve_date_sortie,
    _parse_if_json_string,
    _heures_sup_conjoncturelles_from_monthly_inputs,
)
from app.modules.monthly_inputs.domain.rules import alertes_de_doublon_de_prime
from app.modules.payroll.documents.saisies_du_bulletin import ranger_les_saisies
from app.modules.payroll.documents.plafond_transport import alertes_plafond_transport
from app.modules.schedules.domain.conflits_arret import (
    alerte_arret_sans_demande,
    alerte_arrets_contradictoires,
)


def _periode_de_paie_company(company_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "jour_de_fin": company_data.get("paie_jour_de_fin", 4),
        "occurrence": (
            company_data.get("paie_occurrence")
            if company_data.get("paie_occurrence") is not None
            else -2
        ),
    }


def process_payslip_generation_forfait(
    employee_id: str,
    year: int,
    month: int,
    *,
    ijss_brut_override: float | None = None,
    ijss_tracking_meta: dict | None = None,
    bac_a_sable: BacASable | None = None,
    depart_a_zero: dict | None = None,
    contract_period_id: str | None = None,
):
    """
    Génère une fiche de paie pour un employé en forfait jour.
    En bac à sable, le passé vient de l'appelant et rien n'est persisté.

    Cette fonction est similaire à process_payslip_generation mais utilise
    les modules spécifiques au forfait jour (même sortie `depart_a_zero`).
    """
    alerte_depart_zero = None
    files_to_cleanup = []
    dirs_to_cleanup = []
    dossier_de_travail: Path | None = None
    # Replis de calcul notés pendant la génération (voir engine/replis.py).
    alertes_de_repli_generateur: list = []
    jeton_replis = ouvrir_collecte(alertes_de_repli_generateur)
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

        # Un mois d'un contrat rangé par « Nouveau contrat » se calcule sur la
        # fiche que ce contrat avait (type, entrée, fin, durée…) [D4] ; dans un
        # mois partagé, le bulletin de l'ancien contrat la demande par sa clé [D3].
        try:
            employee_data = fiche_du_mois(employee_data, year, month, contract_period_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        employee_data = {
            **employee_data,
            "exit_last_working_day": resolve_date_sortie(employee_data),
        }
        period_block_reason = payslip_employment_period_block_reason(
            employee_data, year, month
        )
        if period_block_reason:
            raise HTTPException(status_code=400, detail=period_block_reason)

        company_id = employee_data.get("company_id")
        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="Ce collaborateur n'est rattaché à aucune entreprise. Complétez sa fiche employé.",
            )

        employee_folder_name = employee_data["employee_folder_name"]
        statut = employee_data.get("statut")
        is_forfait_flag = employee_data.get("is_forfait_jour")

        if not is_forfait_jour(statut, is_forfait_flag):
            from app.modules.payroll.documents.payslip_run_forfait import (
                message_pas_forfait_jour,
            )

            raise HTTPException(
                status_code=400,
                detail=message_pas_forfait_jour(),
            )

        # Variables automatiques avant le bulletin (réglage de la société), comme
        # aux heures ; avant la lecture des saisies du mois.
        from app.modules.payroll.documents.variables_automatiques import (
            variables_automatiques_avant_bulletin,
        )

        variables_automatiques_avant_bulletin(
            str(company_id),
            str(employee_id),
            year,
            month,
            en_bac_a_sable=bac_a_sable is not None,
            contract_period_id=contract_period_id,
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

        saisies_res = variables_du_bulletin(
            supabase, employee_id, year, month, contract_period_id
        )
        # Bac à sable : des saisies qui n'existent qu'en mémoire s'ajoutent à
        # celles du mois (hors bac à sable, rien ne change).
        saisies_res.data = saisies_du_mois(saisies_res.data, bac_a_sable)

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

        from app.modules.payroll.documents.payslip_generator import (
            _stamp_source_absence_conges,
        )

        absences_rows = _stamp_source_absence_conges(planned_data_all_months, employee_id)

        # Activité partielle posée au calendrier : les deux lignes du mois
        # (retenue, indemnité), calculées comme en heures (même fonction), un
        # jour chômé valant 7 h. En mémoire seulement : le calendrier fait foi.
        from app.modules.activite_partielle.application.service import (
            lignes_du_calendrier,
        )

        # Jours après la sortie écartés, comme en heures : ils sont déjà
        # retenus par la sortie, ils ne sont ni chômés ni indemnisés.
        from app.modules.payroll.application import planning_apres_sortie

        from app.shared.infrastructure.forfait_jour import bornes_periode_de_paie

        sortie_du_contrat = planning_apres_sortie.date_de_sortie(
            employee_data.get("exit_last_working_day")
        )
        prevu_ap, reel_ap, jours_apres_sortie = planning_apres_sortie.ecarter_apres_la_sortie(
            planned_data_all_months,
            actual_data_all_months,
            sortie_du_contrat,
        )
        # Le bulletin dit les jours du planning laissés après la sortie, comme
        # aux heures : le prorata de sortie les retient, rien n'y est compté.
        alerte_apres_sortie = planning_apres_sortie.alerte_planning_apres_sortie(
            jours_apres_sortie, sortie_du_contrat, year, month
        )
        # Les jours de la période de paie de la société, comme les jours
        # d'absence au forfait, hors jours payés avant la reprise ; au mois de
        # sortie, jusqu'au dernier jour du contrat (A9, 18/11).
        from app.shared.domain.periode_variables import fin_au_depart

        debut_ap, fin_ap = bornes_periode_de_paie(
            {"periode_de_paie": _periode_de_paie_company(company_data)}, year, month
        )
        # Les saisies telles que lues (base, et bac à sable s'il y en a un) :
        # l'empreinte d'entrée porte sur elles, pas sur la liste que le
        # calendrier complète. Les lignes d'activité partielle n'existent pas en
        # base : hachées, elles rendaient le bulletin « à recalculer » dès sa
        # génération (24/11/2026). Le calendrier, d'où elles sont tirées, est
        # déjà haché. Sans jour d'activité partielle, la liste est la même.
        saisies_lues = list(saisies_res.data or [])
        saisies_res.data, alerte_activite_partielle = lignes_du_calendrier(
            str(company_id),
            {**employee_data, "is_forfait_jour": True},
            year,
            month,
            prevu_ap,
            reel_ap,
            list(saisies_res.data or []),
            bornes=(debut_ap, fin_au_depart(fin_ap, year, month, sortie_du_contrat)),
        )

        last_day = calendar.monthrange(year, month)[1]
        # Arrêts : mêmes alertes qu'en heures. Un « Arrêt maladie » posé au
        # calendrier sans demande est retenu sans maintien ni IJSS : on le dit.
        alerte_subrogation = alerte_arrets_contradictoires(
            absences_rows, date(year, month, 1), date(year, month, last_day)
        )
        alerte_arret_sans_type = alerte_arret_sans_demande(
            planned_data_all_months,
            absences_rows,
            date(year, month, 1),
            date(year, month, last_day),
        )
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

        # Une seule fonction range les saisies, pour les deux générateurs (audit du 17/11).
        net_a_payer_only_correction_total, reports_nap_negatif = ranger_les_saisies(
            saisies_res.data, saisies_data, company_data
        )

        hs_conj_25, hs_conj_50 = _heures_sup_conjoncturelles_from_monthly_inputs(
            saisies_res.data or []
        )
        if hs_conj_25 is not None:
            saisies_data["heures_supplementaires_conjoncturelles"] = hs_conj_25
        if hs_conj_50 is not None:
            saisies_data["heures_supplementaires_conjoncturelles_50"] = hs_conj_50

        if expense_reports_res.data:
            # Hors montant net social, sauf réglage de la société (Colorplast, S27).
            notes_dans_mns = notes_de_frais_dans_le_mns(company_data)
            for expense in expense_reports_res.data:
                saisies_data["primes"].append(
                    entree_de_note_de_frais(expense, dans_le_mns=notes_dans_mns)
                )

        # Les avances et acomptes du module « Avances » ne passent pas par le
        # moteur : l'enrichissement d'après enregistrement les retient du net, une
        # fois. (Ce bloc lisait `monthly_repayment_amount`, colonne inexistante :
        # il ne retenait jamais rien. Supprimé pour qu'aucune correction de nom ne
        # rouvre le double prélèvement du générateur heures, audit 04/10/2026.)

        if net_a_payer_only_correction_total:
            saisies_data["acompte"] = net_a_payer_only_correction_total
        if reports_nap_negatif:
            saisies_data[CLE_REPORTS_NAP_NEGATIF] = reports_nap_negatif

        # Prime de partage de la valeur : mêmes lectures qu'à l'heure.
        from app.modules.payroll.documents.ppv_donnees import (
            CLE_SAISIES as CLE_SAISIES_PPV,
            donnees_ppv_du_mois,
        )

        donnees_ppv = donnees_ppv_du_mois(
            supabase, employee_id, year, month, company_data, saisies_res.data or []
        )
        if donnees_ppv is not None:
            saisies_data[CLE_SAISIES_PPV] = donnees_ppv

        # --- ÉTAPE 3 : PRÉPARATION DES FICHIERS TEMPORAIRES ---
        # Un dossier propre à cette génération (voir dossier_de_travail.py).
        employee_path = nouveau_dossier_de_travail(employee_folder_name)
        dossier_de_travail = employee_path
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
                # Nom d'usage prioritaire sur le bulletin (pratique paie) ; la DSN
                # garde le nom de naissance (dsn_export lit la base, pas ce fichier).
                "nom": employee_data.get("nom_usage") or employee_data.get("last_name"),
                "prenom": employee_data.get("first_name"),
                "nir": employee_data.get("nir"),
                "date_naissance": employee_data.get("date_naissance"),
                "sexe": employee_data.get("sexe"),
                "matricule": employee_data.get("matricule"),
                "mode_paiement": employee_data.get("salary_payment_method"),
                "adresse": _parse_if_json_string(employee_data.get("adresse")),
            },
            "contrat": {
                "date_entree": employee_data.get("hire_date"),
                "emploi": employee_data.get("job_title"),
                "seniority_reference_date": employee_data.get(
                    "seniority_reference_date"
                ),
                "type_contrat": employee_data.get("contract_type"),
                "date_conclusion_contrat": employee_data.get(
                    "date_conclusion_contrat"
                ),
                "date_debut_execution": employee_data.get("date_debut_execution"),
                "date_fin_contrat": employee_data.get("contract_end_date"),
                "date_sortie": resolve_date_sortie(employee_data),
                "statut": statut,
                "is_forfait_jour": bool(is_forfait_flag),
                "temps_travail": {"duree_hebdomadaire": duree_hebdo},
            },
            "remuneration": {
                "salaire_de_base": {"valeur": salaire_base_valeur},
                "classification_conventionnelle": normalize_classification_for_payroll(
                    employee_data.get("classification_conventionnelle", {})
                ),
                "convention_collective": build_convention_collective_payload(
                    employee_data,
                    company_data,
                    # La convention de la société en vigueur à la fin du mois.
                    a_la_date=fin_du_mois(year, month),
                ),
                "avantages_en_nature": employee_data.get("avantages_en_nature") or {},
            },
            "specificites_paie": resolve_monthly_specificites(
                employee_data.get("specificites_paie", {}),
                year,
                month,
            ),
            "saisie_du_mois": saisies_data,
        }

        try:
            from app.modules.payroll.application.salary_evolution_payroll import (
                prepare_salary_evolution_for_payslip,
            )

            salary_evo = prepare_salary_evolution_for_payslip(
                employee_id, str(company_id), year, month,
                persister=bac_a_sable is None,
            )
            if salary_evo:
                remuneration = contrat_json_content.setdefault("remuneration", {})
                if salary_evo.get("salaire_de_base"):
                    remuneration["salaire_de_base"] = salary_evo["salaire_de_base"]
                if salary_evo.get("evolution_salaire_mois"):
                    remuneration["evolution_salaire_mois"] = salary_evo[
                        "evolution_salaire_mois"
                    ]
        except LectureIndispensable:
            # Salaire ou historique illisible : le bulletin n'est pas calculé,
            # plutôt que payé au salaire de la fiche sans prorata ni rappel.
            raise
        except Exception as evo_err:
            logger.warning(f"Erreur résolution évolution salaire (forfait): {evo_err}")
            from app.modules.payroll.engine.replis import CODE_REPLI_EVOLUTION_SALAIRE, noter_repli

            noter_repli(CODE_REPLI_EVOLUTION_SALAIRE)

        from app.modules.employee_loans.application.payroll_integration import (
            inject_loan_benefit_in_kind,
        )

        contrat_json_content = inject_loan_benefit_in_kind(
            contrat_json_content, employee_id, year, month
        )

        # Dernier mois d'un CDD : ce qu'un contrat précédent a laissé dans le cumul
        # sort de la base de l'indemnité de fin de contrat (L1243-8 ; audit du
        # 03/11/2026, F 2).
        # Le bulletin d'un contrat rangé [D3] garde le cumul de son contrat.
        base_precarite = None if contract_period_id else base_precarite_du_bulletin(
            {**employee_data, "id": employee_data.get("id") or employee_id}, year, month, supabase
        )
        if base_precarite is not None:
            contrat_json_content["contrat"]["cumul_avant_le_contrat"] = base_precarite

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
                    "naf_ape": company_data.get("naf_ape")
                    or company_data.get("code_naf"),
                    "forme_juridique": company_data.get("legal_form"),
                    "adresse": {
                        "rue": company_data.get("adresse_rue"),
                        "code_postal": company_data.get("adresse_code_postal"),
                        "ville": company_data.get("adresse_ville"),
                    },
                },
                "parametres_paie": {
                    "idcc": company_data.get("idcc"),
                    "effectif": effectif_retenu(company_data, year).valeur,
                    "periode_de_paie": _periode_de_paie_company(company_data),
                    # Quand payer — indépendant de la date à laquelle la
                    # gestionnaire de paie arrête les variables.
                    "date_paiement": (company_data.get("settings") or {}).get(
                        "date_paiement"
                    ),
                    "taux_specifiques": {
                        "taux_at_mp": company_data.get("taux_at_mp"),
                        "taux_versement_mobilite": company_data.get("taux_vm"),
                        "taux_fnal": company_data.get("taux_fnal"),
                        "taux_assurance_chomage": (company_data.get("settings") or {}).get(
                            "taux_assurance_chomage"
                        ),
                    },
                    "jei": jei_bloc,
                    "prime_anciennete": prime_anciennete_overrides or None,
                    # Mêmes réglages société qu'en mode horaire : journée de
                    # solidarité (férié travaillé) et diviseur de valorisation
                    # d'une journée d'absence en forfait (21,67 par défaut).
                    "jour_solidarite": (company_data.get("settings") or {}).get(
                        "jour_solidarite"
                    ),
                    "forfait_jours_ouvres_mois": (company_data.get("settings") or {}).get(
                        "forfait_jours_ouvres_mois"
                    ),
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

        # ⚠ `cumuls_res.data.get("cumuls")` est déjà la valeur CANONIQUE de la
        # colonne (`{"cumuls": {...}, "periode": {...}}`, cf. le chemin
        # "heures" équivalent dans `payslip_generator.py` qui l'écrit tel
        # quel) — l'envelopper une seconde fois ici cassait tout mécanisme
        # lisant `contexte.cumuls.cumuls.X` (ex. `brut_reference_n_1` pour
        # l'arbitrage CP 1/10e, cf. salarié 218 Lewis mai 2026 : le 1/10e était
        # toujours à 0 malgré la donnée correctement injectée en base, faute
        # de ce double-enveloppage). Fix : ne plus ré-envelopper, comme le
        # chemin heures.
        previous_cumuls_data = (
            (cumuls_res.data or {}).get("cumuls") if cumuls_res else None
        )
        # Les cumuls du mois d'avant tels que lus : leur empreinte, posée sur le
        # bulletin, dira s'il a été recalculé depuis (voir empreinte_entrees.py).
        cumuls_lus_au_mois_precedent = (
            bac_a_sable.cumuls_precedents if bac_a_sable is not None else previous_cumuls_data
        )
        if bac_a_sable is not None:
            previous_cumuls_data = cumuls_de_depart(bac_a_sable, year)
        elif not isinstance(previous_cumuls_data, dict) or not previous_cumuls_data:
            # Même règle que le chemin heures : un cumul absent ou vide ne vaut pas zéro.
            raison = raison_de_cumul_manquant(
                str(company_id), employee_id, year, month, cumul_trouve=False
            )
            if raison and not (isinstance(raison, RepriseNonPosee) and depart_a_zero):
                raise HTTPException(status_code=422, detail=detail_du_refus(raison))
            if raison:
                alerte_depart_zero = alerte_depart_a_zero(depart_a_zero)
            previous_cumuls_data = {"cumuls": {}, "periode": {}}
        # Premier mois d'un contrat : même règle que le chemin heures.
        previous_cumuls_data = cumuls_precedents_du_contrat(
            previous_cumuls_data,
            employee_data,
            year,
            month,
            {"cumuls": {}, "periode": {}},
        )
        from app.modules.payroll.infrastructure.reference_dixieme import preparer_cumuls_dixieme

        previous_cumuls_data = preparer_cumuls_dixieme(
            supabase, employee_data, str(company_id), year, month, previous_cumuls_data,
            contract_period_id=contract_period_id,
        )

        write_temp_json(
            employee_path / "cumuls" / f"{prev_month:02d}.json", previous_cumuls_data
        )

        # Arrêt arrivé après la validation du bulletin précédent : le moteur le
        # reprend à ses dates (il analyse lui-même les jours du forfait), et ne
        # recompte pas les jours que le bulletin suivant a déjà repris (Elsa, 26/11).
        saisies_data.update(
            arrets_reportes.preparer_le_report(
                supabase,
                employee_id,
                year,
                month,
                forfait_jours=True,
                company_data=company_data,
                planned_calendar_du_mois=(db_data_map.get((year, month)) or {}).get(
                    "planned_calendar"
                ),
                saisies=saisies_lues,
            ).vers_les_saisies()
        )
        write_temp_json(employee_path / "saisies" / f"{month:02d}.json", saisies_data)

        # --- ÉTAPE 4 : GÉNÉRATION IN-PROCESS (app uniquement) ---
        engine_root = payroll_engine_root()
        from app.modules.payroll.documents.payslip_run_forfait import (
            run_payslip_generation_forfait,
        )

        # Métallurgie (art. 103.5.1) : l'activité partielle ne fait pas baisser
        # le net d'un forfait jours ; le complément est cherché par des calculs
        # sans PDF, puis le bulletin est calculé une fois pour de bon.
        from app.modules.payroll.engine import maintien_net_activite_partielle as maintien_ap

        idcc_du_bulletin = (
            (contrat_json_content.get("remuneration") or {}).get("convention_collective") or {}
        ).get("idcc")
        if maintien_ap.s_applique(idcc_du_bulletin, saisies_data.get("primes") or []):
            primes_du_mois = list(saisies_data.get("primes") or [])

            def _net_avec(primes: list[dict[str, Any]]) -> float:
                write_temp_json(
                    employee_path / "saisies" / f"{month:02d}.json",
                    {**saisies_data, "primes": primes},
                )
                return maintien_ap.net_avant_impot(
                    run_payslip_generation_forfait(
                        employee_path,
                        year,
                        month,
                        engine_root,
                        company_id=str(company_id),
                        employee_id=str(employee_id),
                        persister=False,
                    )
                )

            complement = maintien_ap.complement_qui_garde_le_net(primes_du_mois, _net_avec)
            saisies_data["primes"] = maintien_ap.avec_complement(primes_du_mois, complement)
            write_temp_json(employee_path / "saisies" / f"{month:02d}.json", saisies_data)

        payslip_json_data = run_payslip_generation_forfait(
            employee_path,
            year,
            month,
            engine_root,
            company_id=str(company_id),
            employee_id=str(employee_id),
            persister=bac_a_sable is None,
        )

        if ijss_tracking_meta:
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["ijss_tracking"] = ijss_tracking_meta

        if alertes_de_repli_generateur and isinstance(payslip_json_data, dict):
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = fusionner_replis(
                payslip_json_data.get("alertes_baremes"), alertes_de_repli_generateur
            )
        for alerte_du_calendrier in (
            alerte_apres_sortie,
            alerte_subrogation,
            alerte_arret_sans_type,
            alerte_activite_partielle,
        ):
            if alerte_du_calendrier and isinstance(payslip_json_data, dict):
                payslip_json_data = dict(payslip_json_data)
                payslip_json_data["alertes_baremes"] = [
                    *(payslip_json_data.get("alertes_baremes") or []),
                    alerte_du_calendrier,
                ]
        alertes_doublons = alertes_de_doublon_de_prime(saisies_res.data or [])
        if alertes_doublons and isinstance(payslip_json_data, dict):
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = [
                *(payslip_json_data.get("alertes_baremes") or []),
                *alertes_doublons,
            ]
        alerte_effectif_annee = alerte_effectif(effectif_retenu(company_data, year))
        if alerte_effectif_annee and isinstance(payslip_json_data, dict):
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = [
                *(payslip_json_data.get("alertes_baremes") or []),
                alerte_effectif_annee,
            ]
        alerte_franchissement = alerte_franchissement_seuil(company_data, year)
        if alerte_franchissement and isinstance(payslip_json_data, dict):
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = [
                *(payslip_json_data.get("alertes_baremes") or []),
                alerte_franchissement,
            ]
        if alerte_depart_zero and isinstance(payslip_json_data, dict):
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = [
                *(payslip_json_data.get("alertes_baremes") or []),
                alerte_depart_zero,
            ]
            payslip_json_data[CLE_DEPART_A_ZERO] = dict(depart_a_zero)
        # Ce que la fiche oublie (prévoyance que la loi impose, mutuelle…) : le
        # bulletin le dit (posé par la commande, voir alertes_d_entree.py).
        alertes_fiche = [] if bac_a_sable else alertes_d_entree_courantes()
        if alertes_fiche and isinstance(payslip_json_data, dict):
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = [
                *(payslip_json_data.get("alertes_baremes") or []),
                *alertes_fiche,
            ]

        from app.modules.payroll.application.empreinte_entrees_service import (
            poser_empreinte_depuis_lectures,
        )
        from app.modules.payroll.application.periode_variables_service import (
            resoudre_fenetre_variables,
        )

        fenetre = resoudre_fenetre_variables(
            str(company_id), year, month, societe=company_data
        )
        # Les pièces lues pour ce calcul : l'empreinte d'entrée, puis
        # l'empreinte complémentaire du bulletin enregistré, partent d'elles.
        lectures_du_calcul = dict(
            year=year,
            month=month,
            calendriers=db_data_map,
            absences=absences_rows,
            saisies=saisies_lues,
            employee=employee_data,
            company=company_data,
            notes_de_frais=(expense_reports_res.data or []) if expense_reports_res else [],
            fenetre_variables={
                "debut": fenetre.debut.isoformat(),
                "fin": fenetre.fin.isoformat(),
            },
        )
        payslip_json_data = poser_empreinte_depuis_lectures(
            payslip_json_data if isinstance(payslip_json_data, dict) else {},
            **lectures_du_calcul,
        )
        from app.modules.payroll.domain.empreinte_entrees import (
            empreinte_cumuls,
            poser_empreinte_cumuls,
        )

        payslip_json_data = poser_empreinte_cumuls(
            payslip_json_data, empreinte_cumuls(cumuls_lus_au_mois_precedent)
        )

        # --- ÉTAPE 5 : SAUVEGARDER ---

        new_cumuls_path = employee_path / "cumuls" / f"{month:02d}.json"
        new_cumuls_json = (
            json.loads(new_cumuls_path.read_text(encoding="utf-8"))
            if new_cumuls_path.exists()
            else {}
        )
        files_to_cleanup.append(new_cumuls_path)

        if bac_a_sable is not None:
            # Bac à sable : rien n'est persisté — ni storage, ni `payslips`, ni
            # cumuls, ni repos compensateur, ni prêts. Le bulletin et ses cumuls
            # sont rendus à l'appelant, qui chaîne lui-même ses mois.
            files_to_cleanup.append(employee_path / "bulletins" / f"Bulletin_{employee_folder_name}_{month:02d}-{year}_FORFAIT.pdf")
            from app.modules.payroll.engine.controles_convention import (
                avertissements_de_generation,
            )
            from app.modules.payslips.infrastructure.payslip_list_meta import (
                montants_du_bulletin,
            )

            return {
                "status": "success",
                "message": "Bulletin calculé en bac à sable : rien n'a été écrit.",
                "download_url": None,
                "payslip_id": None,
                "payslip_data": payslip_json_data,
                "cumuls": new_cumuls_json,
                "warnings": avertissements_de_generation(payslip_json_data),
                **montants_du_bulletin(payslip_json_data),
            }

        # Un hash par partie (mutuelle, congés, départ, salaire daté…), lu après
        # le calcul : il dira ce qui a changé depuis. Pas en bac à sable.
        from app.modules.payroll.application.empreinte_entrees_service import (
            poser_empreinte_complementaire_depuis_lectures,
        )

        payslip_json_data = poser_empreinte_complementaire_depuis_lectures(
            payslip_json_data, **lectures_du_calcul
        )
        # Un mois passé relit la fiche d'aujourd'hui : on le dit quand elle a changé.
        from app.modules.payroll.application.empreinte_entrees_service import (
            alerte_mois_passe_fiche_du_jour,
        )

        alerte_mois_passe = (
            None
            if contract_period_id
            else alerte_mois_passe_fiche_du_jour(
                payslip_json_data, employee_id=str(employee_id), year=year, month=month
            )
        )
        if alerte_mois_passe:
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = [
                *(payslip_json_data.get("alertes_baremes") or []),
                alerte_mois_passe,
            ]
        # Plafond annuel d'exonération des trajets domicile-travail : une alerte,
        # jamais un changement du bulletin ; même fonction aux deux générateurs.
        # Posée avant l'enregistrement : elle restait dans la seule réponse (A8).
        alertes_transport = alertes_plafond_transport(
            supabase, employee_id, employee_data, year, month
        )
        if alertes_transport:
            payslip_json_data = dict(payslip_json_data)
            payslip_json_data["alertes_baremes"] = [
                *(payslip_json_data.get("alertes_baremes") or []),
                *alertes_transport,
            ]

        # Le moteur imprime sous le nom du mois ; le bulletin d'un contrat rangé
        # est publié sous un nom à lui [D3].
        suffixe = "_FORFAIT" + suffixe_du_pdf(contract_period_id)
        local_pdf_path = (
            employee_path
            / "bulletins"
            / f"Bulletin_{employee_folder_name}_{month:02d}-{year}_FORFAIT.pdf"
        )
        pdf_name = f"{local_pdf_path.stem}{suffixe_du_pdf(contract_period_id)}.pdf"
        pdf_remplace = chemin_enregistre(
            supabase, str(company_id), employee_id, year, month, contract_period_id
        )
        files_to_cleanup.append(local_pdf_path)
        # Le HTML imprimé, gardé à côté du PDF par le moteur (lot 43).
        files_to_cleanup.append(local_pdf_path.with_suffix(".html"))

        exiger_le_pdf_imprime(local_pdf_path)
        storage_path = chemin_horodate(str(company_id), employee_id, pdf_name)
        with open(local_pdf_path, "rb") as f:
            supabase.storage.from_("payslips").upload(
                path=storage_path, file=f.read(), file_options={"x-upsert": "true"}
            )

        signed_url_response = supabase.storage.from_("payslips").create_signed_url(
            storage_path, 3600, options={"download": pdf_name}
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
                "contract_period_id": contract_period_id,
                # Date du dernier calcul (l'upsert ne la reposait pas) : les
                # exports déjà faits du mois deviennent « à refaire ».
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict=CONFLIT_BULLETIN,
        ).execute()

        payslip_id = None
        final_payslip_data = payslip_json_data
        if upsert_result.data:
            payslip_id = upsert_result.data[0].get("id")

            from app.modules.employee_loans.application.payroll_integration import (
                PdfRegenConfig,
                enrich_payslip_after_upsert,
            )
            from app.modules.payroll.documents.pdf_du_bulletin import html_imprime

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
                    pdf_name_suffix=suffixe,
                    html_imprime=html_imprime(local_pdf_path),
                ),
            )
            retirer_pdf_remplace(supabase, pdf_remplace, storage_path)

        # Les cumuls du mois sont ceux du contrat qui continue [D3].
        if not contract_period_id:
            from app.modules.payroll.infrastructure.colonnes_paie_du_mois import (
                ecrire_colonnes_paie_du_mois,
            )

            # Attend la fin d'un enregistrement de calendrier en cours (PT409).
            ecrire_colonnes_paie_du_mois(
                supabase, employee_id, year, month, {"cumuls": new_cumuls_json}
            )


        from app.modules.payroll.engine.controles_convention import (
            avertissements_de_generation,
        )
        from app.modules.payslips.infrastructure.payslip_list_meta import (
            montants_du_bulletin,
        )

        rh_warnings = avertissements_de_generation(final_payslip_data)

        return {
            "status": "success",
            "message": "Bulletin forfait jour généré avec succès.",
            "download_url": pdf_url,
            "payslip_id": payslip_id,
            "warnings": rh_warnings,
            **montants_du_bulletin(final_payslip_data),
        }

    except HTTPException:
        raise
    except LectureIndispensable as e:
        # Une donnée du bulletin n'a pas été lue : rien n'est calculé, la phrase
        # dit de réessayer (503, pas une erreur du logiciel).
        raise HTTPException(status_code=503, detail=str(e)) from e
    except PdfNonImprime as e:
        # Rien n'est enregistré : la phrase le dit, plutôt qu'un ancien PDF gardé.
        logger.exception("PDF du bulletin non imprimé")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logging.error(f"Erreur lors de la génération de paie forfait jour: {e}")
        logger.exception("Échec de process_payslip_generation_forfait")
        # Comme aux heures : une phrase, pas le texte brut de l'erreur (relecture du 18/11).
        raise HTTPException(status_code=500, detail=MESSAGE_ERREUR_GENERATION)

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
        supprimer_dossier_de_travail(dossier_de_travail)
        fermer_collecte(jeton_replis)
