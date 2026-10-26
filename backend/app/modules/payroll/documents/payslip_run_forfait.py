# Orchestration génération bulletin forfait jour (ex-generateur_fiche_paie_forfait.py). Source de vérité : app uniquement.
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import calendar
from jinja2 import Environment, FileSystemLoader

from app.modules.payroll.engine.analyser_jours_forfait import (
    analyser_jours_forfait_du_mois,
)
from app.modules.payroll.engine.bulletin import creer_bulletin_final, creer_bulletin_sortie
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.calcul_cotisations import (
    calculer_cotisations,
    ratio_plafond_periode,
)
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.corrections_manuelles import (
    JournalDesCorrections,
    ajouter_regularisations,
    corriger_les_lignes_de_cotisation,
    corriger_les_lignes_de_gain,
    poser_les_corrections_en_attente,
    synchroniser_le_maintien,
)
from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_reduction_generale,
    heures_reduction_forfait_jours,
    heures_retablies_par_les_rappels_de_maintien,
    rapport_salaires_forfait_jours,
)
from app.modules.payroll.engine.lectures import lire_ou_arreter
from app.modules.payroll.engine.ijss_bulletin import build_rappel_ijss_net_prime
from app.modules.payroll.engine.frais_professionnels import ligne_de_frais_professionnels
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
    controler_annee_des_baremes,
)
from app.modules.payroll.engine.calcul_frais import appliquer_exoneration_note_frais
from app.modules.payroll.engine.calcul_brut_forfait import bornes_de_la_sortie
from app.modules.payroll.engine.contexte import ContextePaie
from app.shared.domain.periode_variables import bornes_mois_civil

from .payslip_run_common import (
    creer_calendrier_etendu,
    definir_periode_de_paie,
    mettre_a_jour_cumuls,
    prefetch_jours_maintien_prime,
)
from .payslip_run_heures import (
    _appliquer_maintien_arret_maladie,
    _extraire_arret_pour_maintien,
    poser_les_arrets_connus,
    poser_le_depart_du_mois,
)
from app.modules.payroll.infrastructure.salaires_de_reference import (
    poser_salaires_de_reference,
)
from app.modules.payroll.engine.lien_saisie import lier_a_la_saisie
from app.modules.payroll.engine import legal_constants as lc
from app.modules.payroll.engine.ppv import classer_ppv, est_une_ppv
from app.modules.payroll.documents.ppv_donnees import CLE_SAISIES as CLE_SAISIES_PPV


def poser_le_depart_du_forfait(contexte, employee_id: str, year: int, month: int) -> None:
    """Le départ du bulletin forfait : celui dont le dernier jour tombe dans le
    mois civil (et non dans la période glissante de la société), comme au
    moteur des heures, au bandeau de la Paie et au reçu ([H12]). Les bornes
    restent sur le contexte pour la fin de contrat et le prorata de sortie."""
    debut_mois, fin_mois = bornes_mois_civil(year, month)
    contexte.bornes_du_depart = (debut_mois, fin_mois)
    poser_le_depart_du_mois(contexte, employee_id, year, month, debut_mois, fin_mois)


def message_pas_forfait_jour() -> str:
    """Refus d'un bulletin au forfait jour pour un salarié qui ne l'est pas."""
    return (
        "Ce salarié n'est pas au forfait jour : son bulletin se calcule sur ses heures. "
        "Pour le passer au forfait jour, cochez la case « Forfait jours » sur sa fiche."
    )


def jours_du_forfait_pour_reduction(contexte: ContextePaie, company_id: str | None) -> float:
    """Jours « prévus au forfait du salarié » (BOSS, allègements généraux, § 860).

    D'abord le forfait propre au salarié, déjà réduit de ses congés d'ancienneté
    quand la société le prévoit (`forfait_annual_days_adjusted`, posé plus haut
    dans ce calcul) ; sinon le forfait de la société, celui que l'application
    retient aussi pour ses jours de repos (`company_leave_settings`). Sans
    réglage enregistré, c'est la valeur par défaut de ces réglages. Une lecture
    ratée arrête le calcul : sans ce nombre, le SMIC de la réduction serait faux.
    """
    ajuste = (contexte.contrat or {}).get("forfait_annual_days_adjusted")
    if ajuste:
        return float(ajuste)
    from app.modules.absences.domain.leave_policy import DEFAULT_LEAVE_POLICY

    if not company_id:
        return float(DEFAULT_LEAVE_POLICY.rtt_forfait_annual_days)
    from app.modules.absences.infrastructure import leave_settings_repository

    politique = lire_ou_arreter(
        lambda: leave_settings_repository.get_leave_policy(str(company_id)),
        "Les jours du forfait (réglages des congés) n'ont pas pu être lus",
    )
    return float(politique.rtt_forfait_annual_days)


def heures_reduction_du_mois(
    resultat_brut: Dict[str, Any],
    resultats_maintien: Dict[str, Any] | None,
    jours_du_forfait: float,
) -> float:
    """Heures du SMIC de référence de la réduction générale pour ce bulletin forfait.

    Mois complet : 151,67 h × jours du forfait / 218, quel que soit le nombre de
    jours travaillés (et non plus 7 h par jour travaillé). Absence non payée,
    arrêt sans maintien intégral, entrée ou sortie : corrigé du rapport des
    salaires, maintien employeur compris (CSS D241-7, IV, 3e et 5e alinéas).
    """
    maintien_verse = float(
        ((resultats_maintien or {}).get("maintien", {}) or {}).get("maintien_verse") or 0.0
    )
    rapport = rapport_salaires_forfait_jours(
        float(resultat_brut.get("salaire_forfait_mois") or 0.0),
        float(resultat_brut.get("retenues_absence_mois") or 0.0),
        maintien_verse,
    )
    return heures_reduction_forfait_jours(jours_du_forfait, rapport)


def _preparer_calendrier_enrichi_forfait(
    chemin_employe: Path, annee: int, mois: int
) -> List[Dict[str, Any]]:
    """Prépare le calendrier forfait jour (jours prévus vs réels)."""
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
            if jour_prevu.get("type") == "travail" and heures_prevues == 1:
                jour_final = {
                    "jour": day_num,
                    "type": "absence_injustifiee_base",
                    "heures": 1.0,
                }
            else:
                jour_final = jour_prevu.copy()
        jour_final["jour"] = day_num
        calendrier_final_mois.append(jour_final)
    return calendrier_final_mois


def run_payslip_generation_forfait(
    employee_path: Path,
    year: int,
    month: int,
    engine_root: Path,
    baremes_override: dict | None = None,
    company_id: str | None = None,
    employee_id: str | None = None,
    persister: bool = True,
) -> dict:
    """
    Génère un bulletin forfait jour en processus (sans subprocess).
    Retourne le bulletin_final (dict). Écrit cumuls et PDF sous employee_path.
    `persister=False` (bac à sable) : même calcul, sans impression du PDF.
    """
    employee_folder_name = employee_path.name
    chemin_saisie = employee_path / "saisies" / f"{month:02d}.json"
    if not chemin_saisie.exists():
        raise FileNotFoundError(f"Fichier de saisie introuvable : {chemin_saisie}")

    saisie_du_mois = json.loads(chemin_saisie.read_text(encoding="utf-8"))
    montant_acompte = saisie_du_mois.get("acompte", 0.0)

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
    # Corrections faites à la main depuis le bulletin (théorème, étape 2) : le
    # moteur les pose ligne par ligne, là où chaque ligne naît.
    contexte.corrections_du_mois = JournalDesCorrections.depuis(saisie_du_mois)
    # Barèmes d'une année antérieure au bulletin : refus ; d'une année
    # suivante (décembre recalculé en janvier) : alerte sur le bulletin.
    contexte.alertes_baremes.extend(controler_annee_des_baremes(contexte.baremes, year))
    resolved_employee_id = employee_id or contexte.contrat.get("employee_id")

    if not contexte.is_forfait_jour:
        raise ValueError(message_pas_forfait_jour())

    employee_id = contexte.contrat.get("employee_id")
    # Le `company_id` de l'appelant fait foi (comme sur le chemin horaire, qui
    # n'utilise que le paramètre) ; le contexte n'est qu'un repli. L'écrasement
    # inconditionnel par le contexte annulait un company_id pourtant fourni dès
    # que `entreprise.id`/`contrat.company_id` étaient absents, ce qui désactivait
    # SILENCIEUSEMENT (garde `if company_id:`, sans exception ni log) le moteur de
    # maintien pour tout salarié forfait-jour en arrêt : absence déduite, maintien
    # employeur jamais réinjecté.
    company_id = (
        company_id
        or (contexte.entreprise or {}).get("id")
        or contexte.contrat.get("company_id")
    )
    if employee_id and company_id:
        try:
            from app.modules.absences.application.cp_seniority_queries import (
                get_forfait_annual_days_adjusted,
            )

            forfait_adj = get_forfait_annual_days_adjusted(
                str(employee_id), str(company_id), year
            )
            if forfait_adj is not None:
                contexte.contrat["forfait_annual_days_adjusted"] = forfait_adj
                logging.getLogger(__name__).info(
                    "Forfait annuel ajusté CP ancienneté : %s j (employé %s)",
                    forfait_adj,
                    employee_id,
                )
        except Exception:
            logging.getLogger(__name__).warning(
                "Forfait annuel non ajusté des congés d'ancienneté", exc_info=True
            )
            from app.modules.payroll.engine.replis import CODE_REPLI_FORFAIT_ANCIENNETE, signaler_repli

            signaler_repli(contexte, CODE_REPLI_FORFAIT_ANCIENNETE)

    # La période de la société porte les variables (jours, absences) ; le
    # départ, lui, appartient au bulletin du mois civil de son dernier jour,
    # comme au moteur des heures et à l'écran ([H12]).
    date_debut_periode, date_fin_periode = definir_periode_de_paie(
        contexte, year, month
    )
    contexte.date_debut_periode = date_debut_periode
    contexte.date_fin_periode = date_fin_periode
    if resolved_employee_id:
        poser_le_depart_du_forfait(contexte, str(resolved_employee_id), year, month)
    else:
        contexte.bornes_du_depart = bornes_mois_civil(year, month)
        contexte.cp_fin_de_contrat = None
    logging.info(
        "Période de paie forfait : %s - %s",
        date_debut_periode.strftime("%d/%m/%Y"),
        date_fin_periode.strftime("%d/%m/%Y"),
    )

    calendrier_etendu = creer_calendrier_etendu(
        employee_path, date_debut_periode, date_fin_periode
    )

    if not calendrier_etendu:
        mois_prec = month - 1 or 12
        annee_prec = year - 1 if month == 1 else year
        mois_suiv = month + 1 if month < 12 else 1
        annee_suiv = year + 1 if month == 12 else year
        planned_data_all_months = []
        actual_data_all_months = []
        for a, m in [
            (annee_prec, mois_prec),
            (year, month),
            (annee_suiv, mois_suiv),
        ]:
            chemin_cal_prevu = employee_path / "calendriers" / f"{m:02d}.json"
            chemin_cal_reel = employee_path / "horaires" / f"{m:02d}.json"
            if chemin_cal_prevu.exists():
                prevu_data = json.loads(
                    chemin_cal_prevu.read_text(encoding="utf-8")
                ).get("calendrier_prevu", [])
                for j in prevu_data:
                    j = j.copy()
                    j["annee"] = a
                    j["mois"] = m
                    planned_data_all_months.append(j)
            if chemin_cal_reel.exists():
                reel_data = json.loads(chemin_cal_reel.read_text(encoding="utf-8")).get(
                    "calendrier_reel", []
                )
                for j in reel_data:
                    j = j.copy()
                    j["annee"] = a
                    j["mois"] = m
                    actual_data_all_months.append(j)
        evenements = analyser_jours_forfait_du_mois(
            planned_data_all_months,
            actual_data_all_months,
            year,
            month,
            employee_folder_name,
            date_debut_periode=date_debut_periode,
            date_fin_periode=date_fin_periode,
        )
        calendrier_etendu = []
        for ev in evenements:
            ev_annee = ev.get("annee", year)
            ev_mois = ev.get("mois", month)
            ev_jour = ev.get("jour")
            if ev_jour:
                ev["date_complete"] = date(ev_annee, ev_mois, ev_jour).isoformat()
            calendrier_etendu.append(ev)

    primes_soumises = []
    primes_non_soumises = []
    primes_soumises_impot = []
    catalogue_primes = {p["id"]: p for p in contexte.baremes["primes"]}
    effectif_entreprise = contexte.effectif
    # PPV : données lues par le générateur (PPV de l'année, rémunération des
    # 12 mois d'avant, accord d'intéressement). Sans bulletin d'avant, le
    # salaire du mois tient lieu de rémunération moyenne.
    donnees_ppv = saisie_du_mois.get(CLE_SAISIES_PPV)
    if isinstance(donnees_ppv, dict) and donnees_ppv.get("remuneration_mensuelle_moyenne") is None:
        donnees_ppv["remuneration_mensuelle_moyenne"] = contexte.salaire_base_mensuel
    # Le Smic des 3 Smic : durée légale, sans heures sup, au prorata d'un temps partiel.
    heures_mensuelles_ppv = (lc.DUREE_LEGALE_HEBDO * 52) / 12
    lignes_cotisations_ppv: List[Dict[str, Any]] = []
    for cle in ["primes", "notes_de_frais", "autres"]:
        for saisie in saisie_du_mois.get(cle, []):
            # Remboursement de frais professionnels : versé au net, hors montant net social.
            ligne_frais = ligne_de_frais_professionnels(saisie)
            if ligne_frais is not None:
                primes_non_soumises.append(ligne_frais)
                continue
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
            rappel_ijss_net = build_rappel_ijss_net_prime(
                prime_id=str(prime_id),
                libelle=str(libelle),
                montant=montant,
                baremes_maladie=contexte.baremes.get("maladie"),
            )
            if rappel_ijss_net:
                primes_non_soumises.append(rappel_ijss_net)
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
            regles = catalogue_primes.get(prime_id)
            if regles:
                soumise_cotis = regles.get("soumise_a_cotisations", True)
                soumise_impot_par_defaut = regles.get("soumise_a_impot", True)
            else:
                soumise_cotis = saisie.get(
                    "soumise_a_cotisations", saisie.get("soumise_a_csg", True)
                )
                soumise_impot_par_defaut = saisie.get("soumise_a_impot", True)
            prime_calculee = lier_a_la_saisie(
                {
                    "libelle": libelle,
                    "montant": montant,
                    "prime_id": prime_id,
                },
                saisie,
            )
            if not soumise_cotis and est_une_ppv(prime_id, libelle):
                # PPV, du catalogue ou saisie par son nom : effectif des seuils,
                # 3 Smic, plafond annuel et nombre de primes (`engine.ppv`).
                rangee = classer_ppv(
                    prime_calculee,
                    effectif=effectif_entreprise,
                    donnees=donnees_ppv,
                    smic_horaire=contexte.smic_horaire,
                    heures_mensuelles=heures_mensuelles_ppv,
                    annee=year,
                )
                primes_non_soumises.extend(rangee.non_soumises)
                primes_soumises_impot.extend(rangee.soumises_impot)
                primes_soumises.extend(rangee.soumises)
                lignes_cotisations_ppv.extend(rangee.lignes_cotisations)
                contexte.alertes_baremes.extend(rangee.alertes)
            elif soumise_cotis:
                primes_soumises.append(prime_calculee)
            elif soumise_impot_par_defaut:
                primes_soumises_impot.append(prime_calculee)
            else:
                primes_non_soumises.append(prime_calculee)

    # --- Participation / intéressement (part numéraire) : régime CSG 9,7 % seule ---
    # Exonéré de cotisations sociales, soumis à CSG/CRDS (6,8 % déductible + 2,9 %
    # non déductible) ; part numéraire imposable à l'IR. Traité hors des buckets de
    # primes (pas de cotisations classiques) et injecté dans le calcul des nets —
    # miroir de la logique payslip_run_heures.py (absente ici jusqu'alors, ce qui
    # cassait montant_net_social et/ou net_imposable pour les forfait-jour ayant
    # une participation, cf. salarié 139/salarié 088/salarié 029/salarié 024/salarié 145/salarié 095/salarié 174).
    from app.modules.participation.domain.bulletin_rules import (
        compute_participation_csg,
    )

    participations_calc: List[Dict[str, Any]] = []
    for part in saisie_du_mois.get("participations", []) or []:
        brut_part = float(part.get("brut") or part.get("montant") or 0.0)
        if brut_part <= 0:
            continue
        part_pee = float(part.get("part_pee") or 0.0)
        non_ded, ded, total = compute_participation_csg(brut_part)
        participations_calc.append(
            {
                "libelle": part.get("libelle") or "Participation",
                "brut": round(brut_part, 2),
                "part_pee": round(part_pee, 2),
                "csg_deductible": float(ded),
                "csg_non_deductible": float(non_ded),
                "csg_total": float(total),
                "acompte": float(part.get("acompte") or 0.0),
            }
        )

    arret_prefetch = _extraire_arret_pour_maintien(
        calendrier_etendu, contexte, date_debut_periode, date_fin_periode
    )
    poser_les_arrets_connus(arret_prefetch, company_id, resolved_employee_id, year, month)
    jours_maintien = prefetch_jours_maintien_prime(
        company_id=company_id,
        contexte=contexte,
        arret_data=arret_prefetch,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
    )

    resultat_brut = calculer_salaire_brut_forfait(
        contexte,
        calendrier_saisie=calendrier_etendu,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        primes_saisies=primes_soumises,
        jours_maintien=jours_maintien,
    )
    salaire_brut_calcule = resultat_brut["salaire_brut_total"]
    details_brut = resultat_brut["lignes_composants_brut"]
    remuneration_hs = resultat_brut["remuneration_brute_heures_supp"]
    total_heures_supp = resultat_brut["total_heures_supp"]

    # Arrêt maladie (forfait jour) : maintien employeur + IJSS subrogées.
    resultats_maintien: Dict[str, Any] | None = None
    if company_id:
        arret_data = arret_prefetch
        if arret_data:
            override = saisie_du_mois.get("ijss_brut_override")
            if override is not None:
                arret_data["ijss_brut_override"] = override
            if saisie_du_mois.get("maintien_base_ouvree"):
                # Saisie « IJSS override » : reconstitution d'un bulletin Cegid.
                arret_data["maintien_base_ouvree"] = True
                arret_data["ijss_releve_du_bulletin"] = True
            try:
                from app.modules.maintenance_settings.application.queries import (
                    get_maintenance_settings,
                )
                from app.modules.payroll.engine.maintien_salaire_service import (
                    calculer_maintien,
                )

                settings_maintien = get_maintenance_settings(company_id)
                settings_dict = settings_maintien.model_dump(mode="json")
                poser_salaires_de_reference(arret_data, resolved_employee_id)
                resultats_maintien = calculer_maintien(
                    arret_data,
                    contexte,
                    settings_dict,
                    date_debut_periode,
                    date_fin_periode,
                )
            except Exception:
                logging.exception(
                    "Maintien de salaire non calculé (forfait, company_id=%s)", company_id
                )
                from app.modules.payroll.engine.replis import (
                    CODE_REPLI_MAINTIEN,
                    signaler_repli,
                )

                signaler_repli(contexte, CODE_REPLI_MAINTIEN)
                resultats_maintien = None

    lignes_csg_ijss, ijss_imposables, brut_modifie = _appliquer_maintien_arret_maladie(
        contexte, resultats_maintien, details_brut
    )
    # Lignes de gain posées après le calcul du brut (nuit, pause, maintien) :
    # corrigées ici, puis le brut se refait sur les lignes.
    effet_gains = corriger_les_lignes_de_gain(details_brut, contexte.corrections_du_mois)
    if effet_gains.corrigees:
        brut_modifie = True
        synchroniser_le_maintien(resultats_maintien, details_brut)
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

    # Plafond SS réduit prorata temporis (entrée/sortie, absences non
    # rémunérées) — même règle qu'en mode horaire.
    # Le mois du départ : plafond au prorata du mois civil, comme le salaire.
    contexte.ratio_plafond_ss = ratio_plafond_periode(
        calendrier_etendu,
        *(bornes_de_la_sortie(contexte) or (date_debut_periode, date_fin_periode)),
        contexte,
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

    # Mêmes lignes informatives que le moteur horaire : la participation reste
    # hors brut cotisable, mais doit apparaître sur le bulletin forfait jours.
    for part in participations_calc:
        details_brut.append(
            {
                "libelle": f"{part['libelle']} (brut, exonéré de cotisations)",
                "quantite": None,
                "taux": None,
                "gain": part["brut"],
                "perte": None,
                "is_informative": True,
            }
        )
        lignes_cotisations.extend(
            [
                {
                    "libelle": f"CSG déductible — {part['libelle']}",
                    "base": part["brut"],
                    "taux_salarial": 0.068,
                    "taux_patronal": 0.0,
                    "montant_salarial": part["csg_deductible"],
                    "montant_patronal": 0.0,
                    "is_participation": True,
                },
                {
                    "libelle": f"CSG/CRDS non déductible — {part['libelle']}",
                    "base": part["brut"],
                    "taux_salarial": 0.029,
                    "taux_patronal": 0.0,
                    "montant_salarial": part["csg_non_deductible"],
                    "montant_patronal": 0.0,
                    "is_participation": True,
                },
            ]
        )

    # CSG/CRDS (et forfait social) des PPV non exonérées de tout : lignes du
    # bulletin, hors du total des cotisations du salaire (comme la participation).
    lignes_cotisations.extend(lignes_cotisations_ppv)

    nombre_jours_travailles = resultat_brut.get("nombre_jours_travailles", 0)
    # Plafond du JEI seulement : la réduction générale a sa propre règle.
    heures_equivalentes = nombre_jours_travailles * 7.0
    # SMIC de référence de la réduction générale : la durée du forfait, pas les
    # jours travaillés (7 h × 21 jours = 147 h, quand Quadra et la loi comptent
    # 150,28 h pour 216 jours). Aussi le « Cumul heures » des cumuls, que relit
    # la régularisation du mois suivant.
    jours_du_forfait = jours_du_forfait_pour_reduction(contexte, company_id)
    heures_reduction = heures_reduction_du_mois(resultat_brut, resultats_maintien, jours_du_forfait)
    # Le maintien d'arrêts passés, payé ce mois-ci, en rétablit les heures (BOSS § 800).
    heures_reduction = max(
        0.0,
        heures_reduction
        + heures_retablies_par_les_rappels_de_maintien(
            primes_soumises,
            heures_reduction_forfait_jours(jours_du_forfait),
            contexte.salaire_base_mensuel,
        ),
    )

    ligne_exoneration_jei = calculer_exoneration_jei(
        contexte,
        lignes_cotisations,
        heures_equivalentes,
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
            contexte, salaire_brut_calcule, heures_reduction
        )
        if ligne_reduction_generale:
            lignes_cotisations.append(ligne_reduction_generale)

    # Cotisations posées après `calculer_cotisations` (CSG des IJSS, JEI) :
    # corrigées ici ; la réduction générale l'a été à son calcul.
    effet_cotisations = corriger_les_lignes_de_cotisation(lignes_cotisations, contexte.corrections_du_mois)
    if effet_cotisations.salarial:
        total_salarial = round(total_salarial + effet_cotisations.salarial, 2)

    # Régularisations de cotisation saisies à la main : après la réduction
    # générale, qui ne doit pas les lire ; avant le net, qui lit le total
    # salarial et non les lignes.
    effet_regul = ajouter_regularisations(lignes_cotisations, total_salarial, saisie_du_mois)
    total_salarial = effet_regul.total_salarial

    resultats_nets = calculer_net_et_impot(
        contexte,
        salaire_brut_calcule,
        lignes_cotisations,
        total_salarial,
        primes_non_soumises,
        remuneration_hs,
        montant_acompte,
        primes_soumises_impot,
        participations_calc,
    )
    if participations_calc:
        resultats_nets["participations"] = participations_calc

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

    contexte.evenements_paie = calendrier_etendu

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
            primes_soumises_impot=primes_soumises_impot,
        )

    # Règle 7 : une correction qui n'a pas trouvé sa ligne reste sur le bulletin.
    poser_les_corrections_en_attente(bulletin_final, contexte.corrections_du_mois)

    smic_calcule_mois = (
        contexte.baremes.get("smic", {}).get("cas_general", 0.0) * heures_equivalentes
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
        heures_supplementaires_mois=total_heures_supp,
        heures_remunerees_mois=heures_reduction,
        regularisation_reduction_generale=effet_regul.reduction_generale,
    )

    chemin_cumuls_mis_a_jour = employee_path / "cumuls" / f"{month:02d}.json"
    if chemin_cumuls_mis_a_jour.exists():
        bulletin_final["cumuls"] = json.loads(
            chemin_cumuls_mis_a_jour.read_text(encoding="utf-8")
        )

    from app.modules.payroll.documents.bulletin_view import construire_vue_bulletin
    from app.modules.payroll.domain.report_nap_negatif import CLE_BULLETIN

    if saisie_du_mois.get(CLE_BULLETIN):
        bulletin_final[CLE_BULLETIN] = saisie_du_mois[CLE_BULLETIN]

    # En bac à sable, pas d'impression : le PDF serait jeté sans être lu (lot 31).
    if persister:
        templates_dir = engine_root / "templates"
        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        template = env.get_template("template_bulletin.html")
        html_genere = template.render(vue=construire_vue_bulletin(bulletin_final))

        pdf_filename = (
            employee_path
            / "bulletins"
            / f"Bulletin_{employee_folder_name}_{month:02d}-{year}_FORFAIT.pdf"
        )
        pdf_filename.parent.mkdir(parents=True, exist_ok=True)
        # Le HTML imprimé est gardé à côté du PDF : l'enrichissement ne réimprime
        # que si le bulletin à imprimer a changé (lot 43).
        from app.modules.payroll.documents.pdf_du_bulletin import imprimer_le_bulletin

        imprimer_le_bulletin(html_genere, pdf_filename, base_url=str(engine_root))

    return bulletin_final
