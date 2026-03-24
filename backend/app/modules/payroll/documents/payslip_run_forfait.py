# Orchestration génération bulletin forfait jour (ex-generateur_fiche_paie_forfait.py). Source de vérité : app uniquement.
from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import calendar
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.modules.payroll.engine.analyser_jours_forfait import analyser_jours_forfait_du_mois
from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import calculer_reduction_generale
from app.modules.payroll.engine.contexte import ContextePaie

from .payslip_run_common import (
    creer_calendrier_etendu,
    definir_periode_de_paie,
    mettre_a_jour_cumuls,
)


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
    reels_par_jour = {
        j["jour"]: j for j in horaires_reels_data.get("calendrier", [])
    }
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
) -> dict:
    """
    Génère un bulletin forfait jour en processus (sans subprocess).
    Retourne le bulletin_final (dict). Écrit cumuls et PDF sous employee_path.
    """
    employee_folder_name = employee_path.name
    chemin_saisie = employee_path / "saisies" / f"{month:02d}.json"
    if not chemin_saisie.exists():
        raise FileNotFoundError(f"Fichier de saisie introuvable : {chemin_saisie}")

    saisie_du_mois = json.loads(chemin_saisie.read_text(encoding="utf-8"))
    montant_acompte = saisie_du_mois.get("acompte", 0.0)

    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    chemin_cumuls = employee_path / "cumuls" / f"{prev_month:02d}.json"

    contexte = ContextePaie(
        chemin_contrat=str(employee_path / "contrat.json"),
        chemin_entreprise=str(engine_root / "data" / "entreprise.json"),
        chemin_cumuls=str(chemin_cumuls),
        chemin_data_dir=str(engine_root / "data"),
    )

    if not contexte.is_forfait_jour:
        raise ValueError(
            f"L'employé {employee_folder_name} n'est pas en forfait jour "
            f"(statut: {contexte.statut_salarie}). Utilisez le générateur heures."
        )

    date_debut_periode, date_fin_periode = definir_periode_de_paie(
        contexte, year, month
    )
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
                reel_data = json.loads(
                    chemin_cal_reel.read_text(encoding="utf-8")
                ).get("calendrier_reel", [])
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
            regles = catalogue_primes.get(prime_id)
            if regles:
                soumise_cotis = regles.get("soumise_a_cotisations", True)
                soumise_impot_par_defaut = regles.get("soumise_a_impot", True)
            else:
                soumise_cotis = saisie.get(
                    "soumise_a_cotisations", saisie.get("soumise_a_csg", True)
                )
                soumise_impot_par_defaut = saisie.get("soumise_a_impot", True)
            prime_calculee = {"libelle": libelle, "montant": montant, "prime_id": prime_id}
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

    resultat_brut = calculer_salaire_brut_forfait(
        contexte,
        calendrier_saisie=calendrier_etendu,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        primes_saisies=primes_soumises,
    )
    salaire_brut_calcule = resultat_brut["salaire_brut_total"]
    details_brut = resultat_brut["lignes_composants_brut"]
    remuneration_hs = resultat_brut["remuneration_brute_heures_supp"]
    total_heures_supp = resultat_brut["total_heures_supp"]

    lignes_cotisations, total_salarial = calculer_cotisations(
        contexte, salaire_brut_calcule, remuneration_hs, total_heures_supp
    )

    nombre_jours_travailles = resultat_brut.get("nombre_jours_travailles", 0)
    heures_equivalentes = nombre_jours_travailles * 7.0
    ligne_reduction_generale = calculer_reduction_generale(
        contexte, salaire_brut_calcule, heures_equivalentes
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

    bulletin_final = creer_bulletin_final(
        contexte,
        salaire_brut_calcule,
        details_brut,
        lignes_cotisations,
        resultats_nets,
        primes_non_soumises,
        year,
        month,
    )

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
        / f"Bulletin_{employee_folder_name}_{month:02d}-{year}_FORFAIT.pdf"
    )
    pdf_filename.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_genere, base_url=str(engine_root)).write_pdf(pdf_filename)

    return bulletin_final
