# Orchestration génération bulletin heures (ex-generateur_fiche_paie.py). Source de vérité : app uniquement.
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import calendar
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import calculer_reduction_generale
from app.modules.payroll.engine.contexte import ContextePaie

from .payslip_run_common import (
    creer_calendrier_etendu,
    definir_periode_de_paie,
    mettre_a_jour_cumuls,
)


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
            if (
                jour_prevu.get("type") == "travail"
                and heures_prevues > 0
            ):
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

    prev_month = month - 1 if month > 1 else 12
    year if month > 1 else year - 1
    chemin_cumuls = employee_path / "cumuls" / f"{prev_month:02d}.json"

    contexte = ContextePaie(
        chemin_contrat=str(employee_path / "contrat.json"),
        chemin_entreprise=str(engine_root / "data" / "entreprise.json"),
        chemin_cumuls=str(chemin_cumuls),
        chemin_data_dir=str(engine_root / "data"),
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

    resultat_brut = calculer_salaire_brut(
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
        j.get("heures", 0)
        for j in calendrier_du_mois
        if j.get("type") == "travail"
    )
    heures_sup_conjoncturelles_mois = max(
        0, heures_travaillees_reelles - heures_dues_hors_conges
    )
    heures_contractuelles_mois = round((duree_contrat_hebdo * 52) / 12, 2)
    total_heures_mois = heures_contractuelles_mois + heures_sup_conjoncturelles_mois

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

    return bulletin_final
