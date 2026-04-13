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

from app.modules.payroll.engine.bulletin import creer_bulletin_final
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_reduction_generale,
)
from app.modules.payroll.engine.contexte import ContextePaie

from .payslip_run_common import (
    creer_calendrier_etendu,
    definir_periode_de_paie,
    mettre_a_jour_cumuls,
)


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

    # Moteur maintien (arrêt maladie typé) — sans company_id pas d’accès paramètres entreprise.
    # TODO V1 : proratiser le PSS au prorata jours travaillés / jours du mois si arrêt.
    # TODO V1 : CSG 6,2 % sur ijss_theorique si subrogation_active.
    # TODO V1 : recalcul réduction Fillon si le brut est modifié par l’arrêt.
    resultats_maintien: Dict[str, Any] | None = None
    if company_id:
        arret_data = _extraire_arret_pour_maintien(
            calendrier_etendu, contexte, date_debut_periode, date_fin_periode
        )
        if arret_data:
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
        j.get("heures", 0) for j in calendrier_du_mois if j.get("type") == "travail"
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

    return bulletin_final
