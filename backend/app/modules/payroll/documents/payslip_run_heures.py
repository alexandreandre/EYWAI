# Orchestration génération bulletin heures (ex-generateur_fiche_paie.py). Source de vérité : app uniquement.
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import calendar
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.modules.payroll.engine.bulletin import creer_bulletin_final, creer_bulletin_sortie
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_reduction_generale,
)
from app.modules.payroll.engine.exoneration_jei import (
    calculer_exoneration_jei,
    jei_applicable,
)
from app.modules.jei_settings.infrastructure.exonerations_repository import (
    jei_exonerations_repository,
)
from app.modules.payroll.engine.baremes_loader import (
    commune_entreprise_depuis_donnees,
    comparer_taux_vm_entreprise,
)
from app.modules.payroll.engine.calcul_frais import appliquer_exoneration_note_frais
from app.modules.payroll.engine.contexte import ContextePaie
from app.modules.payroll.engine.ijss_bulletin import compute_ijss_csg_lines

from .payslip_run_common import (
    creer_calendrier_etendu,
    definir_periode_de_paie,
    mettre_a_jour_cumuls,
    prefetch_jours_maintien_prime,
    resolve_exit_state_for_payslip,
)


def _appliquer_maintien_arret_maladie(
    contexte: ContextePaie,
    resultats_maintien: Dict[str, Any] | None,
    details_brut: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], bool]:
    """Réinjecte le maintien employeur et les IJSS subrogées sur le bulletin.

    - Maintien employeur (complément soumis cotisations) : ajouté au brut
      cotisable (ligne de gain) -> cotisations et RGDU recalculées sur ce brut.
    - IJSS subrogées : ajoutées au net imposable (revenu de remplacement) avec
      leur CSG/CRDS (taux dans payroll_config.maladie.csg_ijss).

    Retourne (lignes_csg_ijss, ijss_imposables, brut_modifie).
    """
    if not resultats_maintien:
        return [], [], False

    bloc_maintien = resultats_maintien.get("maintien", {}) or {}
    maintien_verse = float(bloc_maintien.get("maintien_verse") or 0.0)
    subrogation = bool(resultats_maintien.get("subrogation_active"))
    ijss_theorique = float(
        (resultats_maintien.get("ijss", {}) or {}).get("ijss_theorique") or 0.0
    )

    brut_modifie = False
    if maintien_verse > 0:
        details_brut.append(
            {
                "libelle": "Maintien de salaire employeur",
                "quantite": None,
                "taux": None,
                "gain": round(maintien_verse, 2),
                "perte": None,
                "is_maintien_employeur": True,
            }
        )
        brut_modifie = True

    lignes_csg_ijss: List[Dict[str, Any]] = []
    ijss_imposables: List[Dict[str, Any]] = []
    if subrogation and ijss_theorique > 0:
        cfg_maladie = (contexte.baremes.get("maladie", {}) or {})
        lignes_csg_ijss, _, _ = compute_ijss_csg_lines(ijss_theorique, cfg_maladie)
        base = round(ijss_theorique, 2)
        # IJSS = revenu de remplacement : imposable et ajouté au net à payer
        # (avance employeur), non soumis aux cotisations sociales.
        ijss_imposables.append(
            {
                "prime_id": "ijss_subrogees",
                "libelle": "IJSS subrogées",
                "montant": base,
            }
        )

    return lignes_csg_ijss, ijss_imposables, brut_modifie


def _extraire_arret_pour_maintien(
    calendrier_etendu: List[Dict[str, Any]],
    contexte: ContextePaie,
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any] | None:
    """Construit le dict `arret` attendu par calculer_maintien si un arrêt typé est présent."""
    candidats: list[tuple[date, Dict[str, Any]]] = []
    for ev in calendrier_etendu:
        dc = ev.get("date_complete")
        if not dc:
            continue
        d = date.fromisoformat(str(dc)[:10])
        if not (date_debut_periode <= d <= date_fin_periode):
            continue
        if ev.get("type") != "arret_maladie":
            continue
        if not ev.get("arret_type"):
            continue
        candidats.append((d, ev))
    if not candidats:
        return None
    candidats.sort(key=lambda x: x[0])
    first_ev = candidats[0][1]
    first_d, last_d = candidats[0][0], candidats[-1][0]
    temps_travail = (
        (contexte.contrat or {}).get("contrat", {}).get("temps_travail", {}) or {}
    )
    return {
        "arret_type": first_ev["arret_type"],
        "date_debut": first_d.isoformat(),
        "date_fin": last_d.isoformat(),
        "subrogation_active": bool(first_ev.get("subrogation_active", True)),
        "nombre_enfants": int(first_ev.get("nombre_enfants") or 0),
        "is_temps_partiel": bool(
            first_ev.get("is_temps_partiel")
            if first_ev.get("is_temps_partiel") is not None
            else temps_travail.get("is_temps_partiel", False)
        ),
        "quotite_temps_partiel": float(
            first_ev.get("quotite_temps_partiel")
            or temps_travail.get("quotite", 1.0)
            or 1.0
        ),
        "historique_arrets_annee": first_ev.get("historique_arrets_annee") or [],
        "date_dernier_arret": first_ev.get("date_dernier_arret"),
        "salaire_periode_reelle": float(first_ev.get("salaire_periode_reelle") or 0.0),
    }


def _preparer_calendrier_enrichi(
    chemin_employe: Path, annee: int, mois: int
) -> List[Dict[str, Any]]:
    """Compare prévisionnel et réel pour le mois ; retourne le calendrier enrichi (heures)."""
    chemin_calendrier_prevu = chemin_employe / "calendriers" / f"{mois:02d}.json"
    chemin_horaires_reels = chemin_employe / "horaires" / f"{mois:02d}.json"
    if not chemin_calendrier_prevu.exists():
        raise FileNotFoundError(
            f"Calendrier prévisionnel introuvable : {chemin_calendrier_prevu}"
        )
    calendrier_prevu_data = json.loads(
        chemin_calendrier_prevu.read_text(encoding="utf-8")
    ).get("calendrier_prevu", [])
    horaires_reels_data = (
        json.loads(chemin_horaires_reels.read_text(encoding="utf-8"))
        if chemin_horaires_reels.exists()
        else {}
    )
    prevu_par_jour = {j["jour"]: j for j in calendrier_prevu_data}
    reels_par_jour = {j["jour"]: j for j in horaires_reels_data.get("calendrier", [])}
    calendrier_final_mois = []
    _, num_days = calendar.monthrange(annee, mois)
    for day_num in range(1, num_days + 1):
        jour_prevu = prevu_par_jour.get(day_num, {})
        jour_reel = reels_par_jour.get(day_num)
        if jour_reel:
            jour_final = jour_reel.copy()
        else:
            heures_prevues = jour_prevu.get("heures_prevues", 0.0)
            if jour_prevu.get("type") == "travail" and heures_prevues > 0:
                jour_final = {
                    "jour": day_num,
                    "type": "absence_injustifiee",
                    "heures": heures_prevues,
                }
            else:
                jour_final = jour_prevu.copy()
        jour_final["jour"] = day_num
        calendrier_final_mois.append(jour_final)
    return calendrier_final_mois


def run_payslip_generation_heures(
    employee_path: Path,
    year: int,
    month: int,
    engine_root: Path,
    company_id: str | None = None,
    employee_id: str | None = None,
    baremes_override: dict | None = None,
) -> dict:
    """
    Génère un bulletin heures en processus (sans subprocess).
    Lit les JSON préparés sous employee_path et engine_root, appelle le moteur app.modules.payroll.engine,
    écrit cumuls et PDF, retourne le bulletin_final (dict).
    """
    employee_folder_name = employee_path.name
    chemin_saisie = employee_path / "saisies" / f"{month:02d}.json"
    if not chemin_saisie.exists():
        raise FileNotFoundError(f"Fichier de saisie introuvable : {chemin_saisie}")

    saisie_du_mois = json.loads(chemin_saisie.read_text(encoding="utf-8"))
    montant_acompte = saisie_du_mois.get("acompte", 0.0)
    shift_payroll_summary = saisie_du_mois.get("shift_payroll_summary") or {}

    prev_month = month - 1 if month > 1 else 12
    year if month > 1 else year - 1
    chemin_cumuls = employee_path / "cumuls" / f"{prev_month:02d}.json"

    # entreprise.json isolé par génération (évite la concurrence multi-tenant sur
    # le fichier partagé data/entreprise.json) ; repli sur le partagé si absent.
    chemin_entreprise_isole = employee_path / "entreprise.json"
    chemin_entreprise = (
        chemin_entreprise_isole
        if chemin_entreprise_isole.exists()
        else engine_root / "data" / "entreprise.json"
    )
    contexte = ContextePaie(
        chemin_contrat=str(employee_path / "contrat.json"),
        chemin_entreprise=str(chemin_entreprise),
        chemin_cumuls=str(chemin_cumuls),
        chemin_data_dir=str(engine_root / "data"),
        baremes_override=baremes_override,
    )
    # Aiguillage Fillon (< 2026) / RGDU (>= 2026) et suppression des bandeaux maladie/AF.
    contexte.year = year
    contexte.month = month
    if employee_id:
        contexte.exit_indemnities, contexte.block_iccp_cdd = resolve_exit_state_for_payslip(
            employee_id, year, month
        )

    date_debut_periode, date_fin_periode = definir_periode_de_paie(
        contexte, year, month
    )
    logging.info(
        "Période de paie : %s - %s",
        date_debut_periode.strftime("%d/%m/%Y"),
        date_fin_periode.strftime("%d/%m/%Y"),
    )

    calendrier_etendu = creer_calendrier_etendu(
        employee_path, date_debut_periode, date_fin_periode
    )
    modulation_movement_ids: list[str] = []
    modulation_result = None
    if employee_id and company_id:
        from app.modules.modulation.application.payroll_hook import (
            apply_modulation_hour_account_to_calendar,
        )

        calendrier_etendu, modulation_movement_ids, modulation_result = (
            apply_modulation_hour_account_to_calendar(
                str(company_id),
                employee_id,
                year,
                month,
                calendrier_etendu,
            )
        )
    cet_movement_ids: list[str] = []
    cet_withdrawal_ids: list[str] = []
    if employee_id:
        from app.modules.cet.application.payroll_hook import (
            apply_cet_deposits_to_calendar,
            apply_cet_withdrawals_to_calendar,
        )
        from app.modules.cet.infrastructure.repository import get_cet_settings_row

        calendrier_etendu, cet_movement_ids = apply_cet_deposits_to_calendar(
            employee_id, year, month, calendrier_etendu
        )
        settings_row = get_cet_settings_row(str(company_id or ""))
        hprd = float(settings_row.get("hours_per_rest_day") or 7)
        calendrier_etendu, cet_withdrawal_ids = apply_cet_withdrawals_to_calendar(
            employee_id, year, month, calendrier_etendu, hours_per_rest_day=hprd
        )
    chemin_horaires = employee_path / "horaires" / f"{month:02d}.json"
    saisie_horaires = (
        json.loads(chemin_horaires.read_text(encoding="utf-8"))
        if chemin_horaires.exists()
        else {}
    )
    calendrier_du_mois = saisie_horaires.get("calendrier", [])

    primes_soumises = []
    primes_non_soumises = []
    primes_soumises_impot = []
    catalogue_primes = {p["id"]: p for p in contexte.baremes["primes"]}
    effectif_entreprise = contexte.effectif

    for cle in ["primes", "notes_de_frais", "autres"]:
        for saisie in saisie_du_mois.get(cle, []):
            prime_id = (
                saisie.get("prime_id")
                or saisie.get("libelle", "").replace(" ", "_").lower()
            )
            montant = float(saisie.get("montant", 0.0))
            libelle = (
                saisie.get("libelle")
                or saisie.get("name")
                or prime_id.replace("_", " ")
            )

            is_panier = (
                "panier" in str(prime_id).lower()
                or "repas" in str(prime_id).lower()
                or str(saisie.get("type") or "").lower() == "panier"
            )

            if cle == "notes_de_frais" and montant > 0:
                _exo, reint, _plafond = appliquer_exoneration_note_frais(
                    saisie, contexte.baremes.get("frais_pro")
                )
                if reint > 0:
                    primes_soumises.append(
                        {
                            "libelle": f"Réintégration NDF {libelle}",
                            "montant": reint,
                            "prime_id": "reintegration_ndf",
                        }
                    )
                if _exo and _exo > 0 and _plafond is not None:
                    montant = _exo

            if is_panier and montant > 0 and not saisie.get(
                "soumise_a_cotisations", saisie.get("soumise_a_csg", True)
            ):
                qty = max(1.0, float(saisie.get("quantity") or 1))
                unit = montant / qty if qty else montant
                exo_total = 0.0
                reint_total = 0.0
                for _ in range(int(qty)):
                    exo, reint, plafond = appliquer_exoneration_note_frais(
                        {
                            "montant": unit,
                            "prime_id": prime_id,
                            "type": "panier",
                        },
                        contexte.baremes.get("frais_pro"),
                    )
                    exo_total += exo
                    reint_total += reint
                if reint_total > 0:
                    primes_soumises.append(
                        {
                            "libelle": f"Réintégration panier {libelle}",
                            "montant": round(reint_total, 2),
                            "prime_id": "reintegration_panier",
                        }
                    )
                montant = round(exo_total, 2)

            regles = catalogue_primes.get(prime_id)
            if regles:
                soumise_cotis = regles.get("soumise_a_cotisations", True)
                soumise_impot_par_defaut = regles.get("soumise_a_impot", True)
            else:
                soumise_cotis = saisie.get(
                    "soumise_a_cotisations", saisie.get("soumise_a_csg", True)
                )
                soumise_impot_par_defaut = saisie.get("soumise_a_impot", True)

            prime_calculee = {
                "libelle": libelle,
                "montant": montant,
                "prime_id": prime_id,
            }
            if prime_id == "prime_partage_valeur":
                if effectif_entreprise >= 50:
                    if soumise_cotis:
                        primes_soumises.append(prime_calculee)
                    else:
                        primes_soumises_impot.append(prime_calculee)
                else:
                    if soumise_cotis:
                        primes_soumises.append(prime_calculee)
                    else:
                        primes_non_soumises.append(prime_calculee)
            else:
                if soumise_cotis:
                    primes_soumises.append(prime_calculee)
                elif soumise_impot_par_defaut:
                    primes_soumises_impot.append(prime_calculee)
                else:
                    primes_non_soumises.append(prime_calculee)

    arret_prefetch = _extraire_arret_pour_maintien(
        calendrier_etendu, contexte, date_debut_periode, date_fin_periode
    )
    if company_id:
        from app.modules.modulation.application.payroll_hook import (
            compute_pay_smoothing_gain,
        )

        heures_mens = (contexte.duree_hebdo_contrat * 52) / 12
        taux_est = (
            contexte.salaire_base_mensuel / heures_mens if heures_mens > 0 else 0.0
        )
        contexte.modulation_smoothing_gain = compute_pay_smoothing_gain(
            str(company_id), year, month, taux_est
        )
    jours_maintien = prefetch_jours_maintien_prime(
        company_id=company_id,
        contexte=contexte,
        arret_data=arret_prefetch,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
    )

    resultat_brut = calculer_salaire_brut(
        contexte,
        calendrier_saisie=calendrier_etendu,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        primes_saisies=primes_soumises,
        jours_maintien=jours_maintien,
        actual_hours_raw=calendrier_du_mois,
    )
    salaire_brut_calcule = resultat_brut["salaire_brut_total"]
    details_brut = resultat_brut["lignes_composants_brut"]
    remuneration_hs = resultat_brut["remuneration_brute_heures_supp"]
    total_heures_supp = resultat_brut["total_heures_supp"]

    if shift_payroll_summary:
        # Garde-fou : ne pas cumuler avec une règle per_night_hour (monthly_inputs)
        # sur la même population — préférer ce chemin planning OU la règle variable.
        heures_mens = (contexte.duree_hebdo_contrat * 52) / 12
        taux_horaire = (
            contexte.salaire_base_mensuel / heures_mens if heures_mens > 0 else 0.0
        )
        night_hours = float(shift_payroll_summary.get("night_hours") or 0)
        night_rate = float(shift_payroll_summary.get("night_majoration_rate") or 0.5)
        paid_break = float(shift_payroll_summary.get("paid_break_hours") or 0)
        if night_hours > 0 and taux_horaire > 0:
            taux_nuit = round(taux_horaire * (1 + night_rate), 4)
            gain_nuit = round(night_hours * taux_horaire * night_rate, 2)
            details_brut.append(
                {
                    "libelle": f"Heures de nuit majorées à {night_rate * 100:.0f}%",
                    "quantite": night_hours,
                    "taux": taux_nuit,
                    "gain": gain_nuit,
                    "perte": None,
                }
            )
            salaire_brut_calcule = round(salaire_brut_calcule + gain_nuit, 2)
        if paid_break > 0 and taux_horaire > 0:
            gain_pause = round(paid_break * taux_horaire, 2)
            details_brut.append(
                {
                    "libelle": "Pause rémunérée (planning)",
                    "quantite": paid_break,
                    "taux": round(taux_horaire, 4),
                    "gain": gain_pause,
                    "perte": None,
                }
            )
            salaire_brut_calcule = round(salaire_brut_calcule + gain_pause, 2)

    if modulation_result and modulation_result.hs_credited > 0:
        details_brut.append(
            {
                "libelle": "HS reportées au compte modulation",
                "quantite": modulation_result.hs_credited,
                "taux": None,
                "gain": None,
                "perte": None,
                "is_informative": True,
            }
        )

    # Moteur maintien (arrêt maladie typé) — sans company_id pas d’accès paramètres entreprise.
    # Le maintien employeur est réinjecté dans le brut cotisable ci-dessous, puis
    # les cotisations et la RGDU sont calculées sur le brut corrigé ; les IJSS
    # subrogées sont ajoutées au net avec leur CSG/CRDS.
    resultats_maintien: Dict[str, Any] | None = None
    if company_id:
        arret_data = arret_prefetch
        if arret_data:
            override = saisie_du_mois.get("ijss_brut_override")
            if override is not None:
                arret_data["ijss_brut_override"] = override
            try:
                from app.modules.maintenance_settings.application.queries import (
                    get_maintenance_settings,
                )
                from app.modules.payroll.engine.maintien_salaire_service import (
                    calculer_maintien,
                )

                settings_maintien = get_maintenance_settings(company_id)
                settings_dict = settings_maintien.model_dump(mode="json")
                resultats_maintien = calculer_maintien(
                    arret_data,
                    contexte,
                    settings_dict,
                    date_debut_periode,
                    date_fin_periode,
                )
            except Exception as exc:
                logging.warning(
                    "Maintien de salaire non calculé (company_id=%s): %s",
                    company_id,
                    exc,
                )
                resultats_maintien = None

    # Arrêt maladie : recomposer le brut (maintien employeur soumis cotisations)
    # AVANT cotisations/RGDU ; préparer les IJSS subrogées et leur CSG/CRDS.
    lignes_csg_ijss, ijss_imposables, brut_modifie = _appliquer_maintien_arret_maladie(
        contexte, resultats_maintien, details_brut
    )
    if brut_modifie:
        salaire_brut_calcule = round(
            sum(
                (ligne.get("gain", 0.0) or 0.0)
                for ligne in details_brut
                if not ligne.get("is_sous_total")
            )
            - sum((ligne.get("perte", 0.0) or 0.0) for ligne in details_brut),
            2,
        )

    lignes_cotisations, total_salarial = calculer_cotisations(
        contexte, salaire_brut_calcule, remuneration_hs, total_heures_supp
    )
    if lignes_csg_ijss:
        lignes_cotisations.extend(lignes_csg_ijss)
        total_salarial = round(
            total_salarial
            + sum(ligne.get("montant_salarial", 0.0) or 0.0 for ligne in lignes_csg_ijss),
            2,
        )
    if ijss_imposables:
        primes_soumises_impot = list(primes_soumises_impot) + ijss_imposables

    duree_contrat_hebdo = contexte.duree_hebdo_contrat
    jours_ouvrables_du_mois = sum(
        1 for jour in calendrier_du_mois if jour.get("type") not in ["weekend"]
    )
    heures_theoriques_du_mois = jours_ouvrables_du_mois * (duree_contrat_hebdo / 5)
    jours_de_conges = sum(
        1 for jour in calendrier_du_mois if jour.get("type") == "conges_payes"
    )
    heures_dues_hors_conges = heures_theoriques_du_mois - (
        jours_de_conges * (duree_contrat_hebdo / 5)
    )
    heures_travaillees_reelles = sum(
        j.get("heures", 0) for j in calendrier_du_mois if j.get("type") == "travail"
    )
    heures_sup_conjoncturelles_mois = max(
        0, heures_travaillees_reelles - heures_dues_hors_conges
    )
    heures_contractuelles_mois = (duree_contrat_hebdo * 52) / 12
    total_heures_mois = heures_contractuelles_mois + heures_sup_conjoncturelles_mois

    ligne_exoneration_jei = calculer_exoneration_jei(
        contexte,
        lignes_cotisations,
        total_heures_mois,
        company_id=company_id,
        employee_id=employee_id,
        year=year,
        month=month,
        exonerations_repo=jei_exonerations_repository
        if company_id and employee_id
        else None,
    )
    if ligne_exoneration_jei:
        lignes_cotisations.append(ligne_exoneration_jei)

    ligne_reduction_generale = None
    if not jei_applicable(contexte, year, month):
        ligne_reduction_generale = calculer_reduction_generale(
            contexte, salaire_brut_calcule, total_heures_mois
        )
        if ligne_reduction_generale:
            lignes_cotisations.append(ligne_reduction_generale)

    resultats_nets = calculer_net_et_impot(
        contexte,
        salaire_brut_calcule,
        lignes_cotisations,
        total_salarial,
        primes_non_soumises,
        remuneration_hs,
        montant_acompte,
        primes_soumises_impot,
    )

    taux_vm = (
        contexte.entreprise.get("parametres_paie", {})
        .get("taux_specifiques", {})
        .get("taux_versement_mobilite")
    )
    alerte_vm = comparer_taux_vm_entreprise(
        taux_vm,
        contexte.baremes.get("taux_vmrr"),
        commune=commune_entreprise_depuis_donnees(contexte.entreprise),
    )
    if alerte_vm:
        contexte.alertes_baremes.append(alerte_vm)

    if contexte.exit_indemnities:
        bulletin_final = creer_bulletin_sortie(
            contexte,
            salaire_brut_calcule,
            details_brut,
            lignes_cotisations,
            resultats_nets,
            primes_non_soumises,
            contexte.exit_indemnities,
            year,
            month,
            resultats_maintien=resultats_maintien,
        )
    else:
        bulletin_final = creer_bulletin_final(
            contexte,
            salaire_brut_calcule,
            details_brut,
            lignes_cotisations,
            resultats_nets,
            primes_non_soumises,
            year,
            month,
            resultats_maintien=resultats_maintien,
        )

    smic_calcule_mois = (
        contexte.baremes.get("smic", {}).get("cas_general", 0.0) * total_heures_mois
    )
    pss_du_mois = contexte.baremes.get("pss", {}).get("mensuel", 0.0)
    mettre_a_jour_cumuls(
        contexte,
        salaire_brut_calcule,
        remuneration_hs,
        resultats_nets,
        ligne_reduction_generale,
        month,
        smic_calcule_mois,
        pss_du_mois,
        employee_path,
    )

    chemin_cumuls_mis_a_jour = employee_path / "cumuls" / f"{month:02d}.json"
    if chemin_cumuls_mis_a_jour.exists():
        bulletin_final["cumuls"] = json.loads(
            chemin_cumuls_mis_a_jour.read_text(encoding="utf-8")
        )

    templates_dir = engine_root / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("template_bulletin.html")
    html_genere = template.render(bulletin_final)

    pdf_filename = (
        employee_path
        / "bulletins"
        / f"Bulletin_{employee_folder_name}_{month:02d}-{year}.pdf"
    )
    pdf_filename.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_genere, base_url=str(engine_root)).write_pdf(pdf_filename)

    if employee_id:
        from app.modules.cet.application.payroll_hook import (
            apply_cet_cp_debits_for_payroll,
            finalize_cet_payroll_application,
        )
        from app.modules.modulation.application.payroll_hook import (
            finalize_modulation_payroll_application,
        )

        if modulation_movement_ids:
            finalize_modulation_payroll_application(
                modulation_movement_ids,
                employee_id=employee_id,
                year=year,
                month=month,
            )
        if cet_movement_ids:
            finalize_cet_payroll_application(cet_movement_ids)
        if cet_withdrawal_ids:
            finalize_cet_payroll_application(cet_withdrawal_ids)
        apply_cet_cp_debits_for_payroll(employee_id, year, month)

    if modulation_result:
        bulletin_final["modulation_account"] = {
            "hs_realisees": modulation_result.hs_realisees,
            "hs_credited": modulation_result.hs_credited,
            "hs_paid": modulation_result.hs_paid,
        }

    return bulletin_final
