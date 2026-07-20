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
from app.modules.payroll.planning_repli import appliquer_repli_sans_pointage_par_mois
from app.shared.domain.employment_rules import is_forfait_jour
from app.modules.payroll.application.salary_evolution_payroll import (
    prepare_salary_evolution_for_payslip,
)
from app.modules.payroll.documents.payslip_run_common import (
    regularisation_events_from_calendar,
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


def _is_heures_sup_conjoncturelle_input(row: dict) -> bool:
    """True si la saisie mensuelle porte une quantité d'HS conjoncturelles (pas une prime €)."""
    qty = row.get("payroll_quantity")
    if qty is None:
        return False
    label = " ".join(
        str(row.get(key) or "")
        for key in ("name", "export_code", "description", "catalog_prime_id")
    ).lower()
    if "struct" in label:
        return False
    return (
        ("heure" in label or label.strip().startswith("hs"))
        and ("sup" in label or "hs" in label or "conjonct" in label)
    )


def _is_heures_sup_50_label(row: dict) -> bool:
    """True si la saisie d'HS conjoncturelle précise une majoration à 50 % (sinon 25 % par défaut)."""
    label = " ".join(
        str(row.get(key) or "")
        for key in ("name", "export_code", "description", "catalog_prime_id")
    ).lower()
    return "50" in label


def _heures_sup_conjoncturelles_from_monthly_inputs(
    rows: list[dict],
) -> tuple[float | None, float | None]:
    """Extrait les HS conjoncturelles déclarées (payroll_quantity), scindées 25 %/50 %."""
    total_25 = 0.0
    total_50 = 0.0
    found = False
    for row in rows:
        if _is_heures_sup_conjoncturelle_input(row):
            found = True
            if _is_heures_sup_50_label(row):
                total_50 += float(row["payroll_quantity"])
            else:
                total_25 += float(row["payroll_quantity"])
    if not found:
        return None, None
    return total_25, total_50


def _is_participation_numeraire_input(row: dict) -> bool:
    """True si la saisie mensuelle est une somme de participation/intéressement.

    Le montant (`amount`) est alors traité comme le **brut** de la part numéraire :
    exonéré de cotisations, soumis à CSG/CRDS 9,7 % et imposable IR (régime géré
    par le moteur, cf. `payslip_run_heures`). La part PEE (placée, exonérée IR)
    est exclue ici.
    """
    # Seule une somme positive (le versement) est une part numéraire ; un montant
    # négatif est une retenue (acompte déjà versé), pas une participation à verser.
    if float(row.get("amount") or 0) <= 0:
        return False

    label = " ".join(
        str(row.get(key) or "")
        for key in ("name", "description", "catalog_prime_id", "export_code")
    ).lower()

    # Écarter les lignes connexes qui peuvent mentionner « participation » sans être
    # la somme versée elle-même (acompte/avance, remboursement de frais, PEE).
    exclusions = (
        "acompte",
        "avance",
        "note de frais",
        "remboursement",
        "frais",
        "pee",
        "plan d'épargne",
        "plan d'epargne",
    )
    if any(term in label for term in exclusions):
        return False

    return bool(
        row.get("participation_campaign_id")
        or row.get("participation_bulletin_id")
        or "participation" in label
        or "intéressement" in label
        or "interessement" in label
    )


def _is_net_a_payer_only_correction_input(row: dict) -> bool:
    """True si la saisie est une régularisation qui ne réduit que le NET À
    PAYER du mois (comme un acompte sur salaire), sans toucher au montant net
    social ni au net imposable.

    Deux cas rencontrés, absents de la DSN (vérifié : ni le montant ni le
    libellé n'apparaissent dans les blocs S21.G00.50/54/58 de la DSN réelle
    Colorplast 05/2026), donc purement des ajustements de trésorerie du
    cabinet, hors assiette sociale/fiscale déclarée :
    - « Report NAP négatif » (régularisation d'un trop-versé antérieur,
      cf. Cegid GAUTHERON mai 2026 : -115,11 €).
    - « SMU2 GAN MUTUELLE FAMILLE » (cf. Cegid ESPINOSA/GAUTHERON/GIRERD
      mai 2026 : -98,12 € identique sur les 3, donc indépendant du salaire —
      probablement une régularisation de cotisation mutuelle famille).
    """
    if float(row.get("amount") or 0) >= 0:
        return False
    label = " ".join(
        str(row.get(key) or "") for key in ("name", "description")
    ).lower()
    if "report" in label and "nap" in label:
        return True
    if "mutuelle" in label and "famille" in label:
        return True
    # « Acompte MM/AAAA » (avance sur salaire versée en cours de mois, cf. Cegid
    # MBC mai 2026 : AWAD 300 €, GOISSAUD 500 €, etc.) : réduit uniquement le net
    # à payer, hors assiette sociale/fiscale. On exclut « acompte sur/de
    # participation » (SINT), qui lui réduit aussi le montant net social et suit
    # le mécanisme dédié de la participation.
    if "acompte" in label and "participation" not in label:
        return True
    # « Saisie » (saisie-arrêt sur salaire, ordonnée par tribunal/trésor
    # public) et « Virement salaire du DD/MM » (régularisation d'un virement
    # déjà effectué sur une période antérieure) : purs ajustements de
    # trésorerie, hors assiette sociale/fiscale (cf. Cegid OVIE mai 2026).
    if "saisie" in label:
        return True
    return "virement" in label and "salaire" in label


def _is_cantine_input(row: dict) -> bool:
    """True si la saisie est une retenue « Cantine » (participation salariale aux
    repas). N'entre pas dans l'assiette brute (le brut reste la base sans cantine)
    ni au net imposable, MAIS réduit le montant net social ET le net à payer
    (cf. Cegid GILLET/PORRAL/BOUVIER Mont Blanc Composite mai 2026 : la retenue
    apparaît juste avant la ligne MONTANT NET SOCIAL, qui l'inclut). On la route
    donc comme une prime NON soumise (montant négatif) plutôt qu'un acompte pur
    (net à payer seulement), pour que le MNS la reflète comme chez Cegid."""
    if float(row.get("amount") or 0) >= 0:
        return False
    label = " ".join(str(row.get(key) or "") for key in ("name", "description")).lower()
    return "cantine" in label


def _is_frais_pro_non_soumis_input(row: dict) -> bool:
    """True si la saisie est un remboursement de frais professionnels non soumis
    (panier repas, indemnité de déplacement forfaitaire, etc.) : ajouté au net à
    payer, mais exclu du montant net social et du net imposable (frais pro, pas de
    la rémunération).

    Cf. Cegid ASKARI Mont Blanc Composite mai 2026 : « Paniers Jours non soumis »
    120 € présent au net à payer (1781,38 €) mais absent du montant net social
    (1661,38 €) — écart de 120 € exactement. Même constat sur MEUNIER pour une
    « Indemnité forfaitaire dep. » (déplacement) de 100 €.
    """
    if float(row.get("amount") or 0) <= 0:
        return False
    if row.get("is_socially_taxed", True):
        return False
    label = " ".join(
        str(row.get(key) or "") for key in ("name", "description")
    ).lower()
    # "Remboursement de notes de frais" (dépenses réelles avec justificatif) reste
    # dans le net social normal (cf. Cegid BUGNY mai 2026 : inclus dans le MNS) —
    # seules les indemnités forfaitaires (panier, déplacement forfaitaire) en sont
    # exclues. Exclusion explicite pour ne pas les confondre.
    # « Remboursement de notes de frais » (BUGNY Colorplast) reste dans le MNS ;
    # « Rbst note de frais » (SNDF, LABBE/BORDELIER MBC) est un frais pro hors MNS.
    if "remboursement de note" in label:
        return False
    return any(
        term in label
        for term in ("panier", "indemnité forfaitaire", "indemnite forfaitaire",
                     "déplacement", "deplacement", "rbst note de frais", "note de frais")
    )


def _is_panier_input(row: dict) -> bool:
    """True si la saisie est un panier repas (indemnité de panier)."""
    label = " ".join(
        str(row.get(key) or "") for key in ("name", "description")
    ).lower()
    return "panier" in label


def _is_ijss_override_input(row: dict) -> bool:
    """True si la saisie porte un override d'IJSS subrogées back-calculé depuis le
    bulletin (arrêt maladie avec maintien). Sa présence pilote le moteur maintien :
    - IJSS subrogées forcées au montant fourni (`ijss_brut_override`) ;
    - base de maintien calculée sur les jours ouvrés au salaire réel
      (`maintien_base_ouvree`), conforme au décompte Cegid.

    Cf. SERE/OZEN Mont Blanc Composite mai 2026 : IJSS = absence 100 % − maintien
    du bulletin (non dérivable des seules données CPAM). N'entre ni au brut ni aux
    primes : purement un paramètre du calcul de maintien."""
    label = " ".join(
        str(row.get(key) or "") for key in ("name", "description")
    ).lower()
    return "ijss" in label and "override" in label


def _is_participation_pee_input(row: dict) -> bool:
    """True si la saisie est la part participation/intéressement placée sur un PEE.

    Exonérée de cotisations ET d'IR (seule la CSG/CRDS 9,7 % s'applique) : traitée
    dans le même bucket `participations` que la part numéraire, mais avec
    `part_pee` = montant total (cf. calcul_net._participation_aggregats).
    """
    if float(row.get("amount") or 0) <= 0:
        return False
    label = " ".join(
        str(row.get(key) or "")
        for key in ("name", "description", "catalog_prime_id", "export_code")
    ).lower()
    is_participation = bool(
        row.get("participation_campaign_id")
        or row.get("participation_bulletin_id")
        or "participation" in label
        or "intéressement" in label
        or "interessement" in label
    )
    is_pee = "pee" in label or "plan d'épargne" in label or "plan d'epargne" in label
    return is_participation and is_pee


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


def _build_temps_travail_payload(employee_data: dict) -> dict[str, Any]:
    """Construit le bloc temps_travail du contrat.json paie depuis la fiche salarié."""
    from app.modules.employees.domain.rules import (
        DUREE_LEGALE_HEBDO,
        normalize_temps_travail_fields,
    )

    is_tp, duree = normalize_temps_travail_fields(
        employee_data.get("is_temps_partiel"),
        employee_data.get("duree_hebdomadaire"),
    )
    quotite = round(min(1.0, duree / DUREE_LEGALE_HEBDO), 4) if duree > 0 else 1.0
    return {
        "is_temps_partiel": is_tp,
        "duree_hebdomadaire": duree,
        "quotite": quotite,
    }


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

        try:
            from app.modules.planning.infrastructure.repository import (
                planning_repository,
            )

            planning_settings = planning_repository.get_company_planning_settings(
                str(company_id)
            )
            if planning_settings and planning_settings.get(
                "auto_generate_payroll_variables_before_payslip"
            ):
                from app.modules.payroll_variables.application.generate_monthly import (
                    generate_monthly_variables,
                )

                generate_monthly_variables(str(company_id), year, month, dry_run=False)
        except Exception as auto_var_exc:
            logger.warning(
                "Génération auto variables paie ignorée: %s", auto_var_exc
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
            .select("year, month, planned_calendar, actual_hours, payroll_events")
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

        year_months = [(d["year"], d["month"]) for d in dates_to_process]
        actual_data_all_months = appliquer_repli_sans_pointage_par_mois(
            planned_data_all_months,
            actual_data_all_months,
            year_months,
            is_forfait_jour=is_forfait_jour(employee_data.get("statut")),
        )

        weekly_map = None
        if company_id:
            try:
                from app.modules.modulation.application.reference_resolution import (
                    resolve_effective_weekly_hours_map,
                )

                weekly_map = resolve_effective_weekly_hours_map(
                    str(company_id), year, float(duree_hebdo)
                )
            except Exception:
                weekly_map = None

        payroll_events_list = payroll_analyzer_analyser(
            planned_data_all_months,
            actual_data_all_months,
            duree_hebdo,
            year,
            month,
            employee_folder_name,
            modulation_weekly_hours=weekly_map,
        )
        # Régularisations antérieures (absence/arrêt d'un mois précédent dont la
        # retenue n'est rattachée qu'au bulletin du mois courant, cf. DSN
        # S21.G00.65 / pratique Cegid) : saisie ponctuelle sur le
        # planned_calendar DU MOIS COURANT (jamais sur le mois d'origine, déjà
        # clos/payé), voir `regularisation_events_from_calendar` docstring.
        current_month_row = db_data_map.get((year, month))
        if current_month_row:
            payroll_events_list = payroll_events_list + regularisation_events_from_calendar(
                current_month_row.get("planned_calendar")
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
            modulation_weekly_hours=weekly_map,
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

        current_schedule = db_data_map.get((year, month)) or {}
        payroll_events_raw = current_schedule.get("payroll_events") or {}
        if isinstance(payroll_events_raw, dict):
            summary = payroll_events_raw.get("shift_payroll_summary")
            if isinstance(summary, dict) and summary:
                saisies_data["shift_payroll_summary"] = summary

        paniers_non_soumis_dans_mns = bool(
            (company_data.get("settings") or {}).get("paniers_non_soumis_dans_mns")
        )
        net_a_payer_only_correction_total = 0.0
        for row in saisies_res.data:
            if _is_heures_sup_conjoncturelle_input(row):
                continue
            if _is_cantine_input(row):
                # Retenue repas : réduit MNS + net à payer, hors brut/imposable.
                saisies_data["primes"].append({
                    "prime_id": row.get("catalog_prime_id") or row["name"].replace(" ", "_").lower(),
                    "libelle": row["name"],
                    "montant": float(row["amount"]),
                    "soumise_a_cotisations": False,
                    "soumise_a_impot": False,
                })
                continue
            if _is_net_a_payer_only_correction_input(row):
                net_a_payer_only_correction_total += -float(row["amount"])
                continue
            if _is_frais_pro_non_soumis_input(row):
                # Convention (paramétrable) : selon la CCN, le panier repas non
                # soumis est soit un remboursement de frais professionnels (exclu
                # du montant net social — défaut, ex. CCN plasturgie SPAN), soit un
                # complément de rémunération inclus au MNS et au net à payer (ex.
                # CCN métallurgie panier équipe SPAJ). Piloté par le paramètre
                # entreprise `paniers_non_soumis_dans_mns`.
                if paniers_non_soumis_dans_mns and _is_panier_input(row):
                    saisies_data["primes"].append({
                        "prime_id": row.get("catalog_prime_id")
                        or row["name"].replace(" ", "_").lower(),
                        "libelle": row["name"],
                        "montant": float(row["amount"]),
                        "soumise_a_cotisations": False,
                        "soumise_a_impot": False,
                    })
                    continue
                # Ajout net (signe négatif de l'accumulateur "acompte" = ajout au net
                # à payer, cf. calcul_net._calculer_net_a_payer) sans passer par le
                # brut/les cotisations ni le montant net social.
                net_a_payer_only_correction_total -= float(row["amount"])
                continue
            if _is_ijss_override_input(row):
                saisies_data["ijss_brut_override"] = abs(float(row["amount"]))
                saisies_data["maintien_base_ouvree"] = True
                continue
            if _is_participation_pee_input(row):
                saisies_data.setdefault("participations", []).append(
                    {
                        "libelle": row["name"],
                        "brut": float(row["amount"]),
                        "part_pee": float(row["amount"]),
                    }
                )
                continue
            if _is_participation_numeraire_input(row):
                saisies_data.setdefault("participations", []).append(
                    {
                        "libelle": row["name"],
                        "brut": float(row["amount"]),
                    }
                )
                continue
            catalog_id = row.get("catalog_prime_id")
            prime_id = catalog_id or row["name"].replace(" ", "_").lower()
            prime_entry = {
                "prime_id": prime_id,
                "libelle": row["name"],
                "montant": row["amount"],
                "soumise_a_cotisations": row.get("is_socially_taxed", True),
                "soumise_a_impot": row.get("is_taxable", True),
            }
            if row.get("export_code"):
                prime_entry["export_code"] = row["export_code"]
                ex = str(row["export_code"])
                prime_entry["libelle"] = f"{row['name']} ({ex})"
            if row.get("payroll_quantity") is not None:
                prime_entry["quantity"] = float(row["payroll_quantity"])
            if catalog_id and ("panier" in str(catalog_id).lower() or "repas" in str(catalog_id).lower()):
                prime_entry["type"] = "panier"
            saisies_data["primes"].append(prime_entry)

        hs_conj_25, hs_conj_50 = _heures_sup_conjoncturelles_from_monthly_inputs(
            saisies_res.data or []
        )
        if hs_conj_25 is not None:
            saisies_data["heures_supplementaires_conjoncturelles"] = hs_conj_25
        if hs_conj_50 is not None:
            saisies_data["heures_supplementaires_conjoncturelles_50"] = hs_conj_50

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

            # Remboursement de PRÊT SALARIÉ (table `salary_advances`, distinct des
            # acomptes/saisies saisis en `monthly_inputs`) : un prêt employeur est
            # une transaction financière séparée, pas une avance sur la
            # rémunération du mois restant due — il ne doit donc PAS entrer dans
            # le Montant Net Social (MNS), qui ne reflète QUE la rémunération.
            # Routé comme une prime NON SOUMISE (cotisations/impôt) au montant
            # négatif — mécanisme déjà existant et éprouvé côté forfait-jour
            # (cf. payslip_generator_forfait.py, "remboursement_avance_salaire"),
            # généralisé ici au chemin heures pour cohérence. Ce canal réduit à
            # la fois le net à payer ET le MNS de façon symétrique
            # (`_calculer_net_a_payer` et `calculer_montant_net_social` lisent
            # tous deux `primes_non_soumises`), contrairement à l'ancien canal
            # "acompte" qui ne touchait que le net à payer — comportement
            # volontairement conservé tel quel pour les acomptes/saisies
            # monthly_inputs (vérifié correct sur 5 cas convergés : FEDRIGONI/
            # DICK/MENIN/LACROSSE/BUSIZA, Lewis mai 2026 — ceux-ci ne doivent
            # JAMAIS toucher le MNS, distinction gardée nette).
            if total_advances_repayment > 0:
                saisies_data.setdefault("primes", []).append(
                    {
                        "prime_id": "remboursement_pret_salarie",
                        "libelle": "Remboursement prêt salarié",
                        "montant": -float(total_advances_repayment),
                        "soumise_a_cotisations": False,
                        "soumise_a_impot": False,
                    }
                )
            saisies_data["acompte"] = net_a_payer_only_correction_total
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
                "statut": employee_data.get("statut"),
                "is_forfait_jour": bool(employee_data.get("is_forfait_jour")),
                "emploi": employee_data.get("job_title"),
                "periode_essai": _parse_if_json_string(
                    employee_data.get("periode_essai")
                ),
                "temps_travail": _build_temps_travail_payload(employee_data),
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
                )
                or {},
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
                    "periode_de_paie": {
                        "jour_de_fin": company_data.get("paie_jour_de_fin", 4),
                        "occurrence": (
                            company_data.get("paie_occurrence")
                            if company_data.get("paie_occurrence") is not None
                            else -2
                        ),
                    },
                    "taux_specifiques": {
                        "taux_at_mp": company_data.get("taux_at_mp"),
                        "taux_versement_mobilite": company_data.get("taux_vm"),
                        "taux_fnal": company_data.get("taux_fnal"),
                    },
                    "jei": jei_bloc,
                    "prime_anciennete": prime_anciennete_overrides or None,
                    "jour_solidarite": (company_data.get("settings") or {}).get(
                        "jour_solidarite"
                    ),
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
