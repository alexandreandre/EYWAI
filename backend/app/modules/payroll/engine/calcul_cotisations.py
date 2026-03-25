# moteur_paie/calcul_cotisations.py

import sys
import os
from .contexte import ContextePaie
from typing import Dict, Any, List, Tuple
import json
from supabase import create_client, Client

# Fichier : moteur_paie/calcul_cotisations.py

# Fichier : moteur_paie/calcul_cotisations.py


def _calculer_assiettes(
    contexte: ContextePaie, salaire_brut: float, remuneration_heures_supp: float
) -> Dict[str, float]:
    """Prépare toutes les bases de calcul (assiettes) nécessaires pour les cotisations."""
    pss_mensuel = contexte.baremes.get("pss", {}).get("mensuel", 0.0)
    duree_legale_hebdo = 35.0

    # --- NOUVEAU BLOC : CALCUL DU PLAFOND AU PRORATA ---
    pss_calcule = pss_mensuel
    duree_contrat_hebdo = contexte.duree_hebdo_contrat
    proratiser = (
        contexte.contrat.get("contrat", {})
        .get("temps_travail", {})
        .get("proratiser_plafond_ss", False)
    )

    if proratiser and duree_contrat_hebdo < duree_legale_hebdo:
        # Formule URSSAF : Plafond × (Durée contractuelle / Durée légale)
        # Note : les heures complémentaires ne sont pas encore gérées ici.
        pss_calcule = pss_mensuel * (duree_contrat_hebdo / duree_legale_hebdo)
        print(
            f"INFO: Plafond SS proratisé pour temps partiel : {pss_calcule:.2f} €",
            file=sys.stderr,
        )
    # --- FIN DU NOUVEAU BLOC ---

    # Assiettes conditionnelles
    assiette_tranche_2 = 0.0
    assiette_cet = 0.0
    # On utilise maintenant le pss_calcule (proratisé ou non)
    if salaire_brut > pss_calcule:
        assiette_tranche_2 = max(0, min(salaire_brut, 8 * pss_calcule) - pss_calcule)
        assiette_cet = min(salaire_brut, 8 * pss_calcule)

    # Parts patronales pour la base CSG (inchangé)
    mutuelle_spec = contexte.contrat.get("specificites_paie", {}).get("mutuelle", {})
    if not isinstance(mutuelle_spec, dict):
        mutuelle_spec = {}
    part_patronale_frais_sante = 0.0
    if mutuelle_spec.get("adhesion"):
        # Nouveau format : charger depuis company_mutuelle_types si mutuelle_type_ids présent
        mutuelle_type_ids = mutuelle_spec.get("mutuelle_type_ids", [])
        if mutuelle_type_ids:
            try:
                supabase_url = os.environ.get("SUPABASE_URL")
                supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
                if supabase_url and supabase_key:
                    supabase_client: Client = create_client(supabase_url, supabase_key)
                    mutuelles_response = (
                        supabase_client.table("company_mutuelle_types")
                        .select("*")
                        .in_("id", mutuelle_type_ids)
                        .eq("is_active", True)
                        .execute()
                    )

                    if mutuelles_response.data:
                        for mutuelle in mutuelles_response.data:
                            if mutuelle.get("part_patronale_soumise_a_csg", True):
                                part_patronale_frais_sante += float(
                                    mutuelle.get("montant_patronal", 0.0)
                                )
            except Exception as e:
                print(
                    f"WARN: Impossible de charger les mutuelles pour CSG: {e}",
                    file=sys.stderr,
                )

        # Ancien format : lignes_specifiques (rétrocompatibilité)
        for ligne in mutuelle_spec.get("lignes_specifiques", []):
            # On ajoute la part patronale seulement si la ligne est marquée comme soumise à CSG
            if ligne.get(
                "part_patronale_soumise_a_csg", True
            ):  # True par défaut pour la compatibilité
                part_patronale_frais_sante += ligne.get("montant_patronal", 0.0) or 0.0

    part_patronale_prevoyance = 0.0
    prevoyance_spec = contexte.contrat.get("specificites_paie", {}).get(
        "prevoyance", {}
    )
    if isinstance(prevoyance_spec, dict) and prevoyance_spec.get("adhesion"):
        assiette_prevoyance = min(salaire_brut, pss_calcule)

        if contexte.statut_salarie == "Cadre":
            # Pour les cadres, on somme les parts patronales des lignes spécifiques du contrat
            for ligne in prevoyance_spec.get("lignes_specifiques", []):
                part_patronale_prevoyance += assiette_prevoyance * (
                    ligne.get("patronal", 0.0) or 0.0
                )
        else:
            # Pour les non-cadres, on utilise la règle standard
            cotisation_prevoyance = contexte.get_cotisation_by_id(
                "prevoyance_non_cadre"
            )
            if cotisation_prevoyance and cotisation_prevoyance.get("patronal"):
                part_patronale_prevoyance = (
                    assiette_prevoyance * cotisation_prevoyance["patronal"]
                )

    # CALCUL ASSIETTE CSG (inchangé)
    salaire_brut_hors_hs = salaire_brut - remuneration_heures_supp
    base_csg_normale = (
        (salaire_brut_hors_hs * 0.9825)
        + part_patronale_prevoyance
        + part_patronale_frais_sante
    )
    base_csg_hs = remuneration_heures_supp * 0.9825

    return {
        "brut": salaire_brut,
        "plafond_ss": round(
            pss_calcule, 2
        ),  # On retourne le plafond potentiellement réduit
        "brut_plafonne": min(salaire_brut, pss_calcule),
        "tranche_2": round(assiette_tranche_2, 2),
        "assiette_cet": round(assiette_cet, 2),
        "csg_crds_base_normale": round(base_csg_normale, 2),
        "csg_crds_base_hs": round(base_csg_hs, 2),
    }


def _calculer_une_ligne(
    libelle: str, assiette: float, taux_salarial: float, taux_patronal: float
) -> Dict[str, Any] | None:
    if assiette <= 0 and not (taux_salarial is None and taux_patronal is None):
        return None
    montant_salarial = round(assiette * (taux_salarial or 0.0), 2)
    montant_patronal = round(assiette * (taux_patronal or 0.0), 2)
    if montant_salarial == 0 and montant_patronal == 0:
        return None
    return {
        "libelle": libelle,
        "base": assiette,
        "taux_salarial": taux_salarial,
        "montant_salarial": montant_salarial,
        "taux_patronal": taux_patronal,
        "montant_patronal": montant_patronal,
    }


def calculer_cotisations(
    contexte: ContextePaie,
    salaire_brut: float,
    remuneration_heures_supp: float = 0.0,
    total_heures_supp: float = 0.0,
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Calcule toutes les cotisations sociales, salariales et patronales.
    """
    print("INFO: Démarrage du calcul des cotisations...", file=sys.stderr)

    assiettes = _calculer_assiettes(contexte, salaire_brut, remuneration_heures_supp)
    root_key = next(
        (k for k, v in contexte.baremes["cotisations"].items() if isinstance(v, list)),
        "cotisations",
    )
    liste_cotisations_brutes = contexte.baremes["cotisations"].get(root_key, [])
    bulletin_cotisations = []

    for coti_data in liste_cotisations_brutes:
        coti_id = coti_data.get("id")

        # --- BLOC CORRIGÉ ---
        # On vérifie l'adhésion spécifique du salarié à la prévoyance
        if coti_id in ["prevoyance_cadre", "prevoyance_non_cadre"]:
            continue
        # --- FIN DU BLOC ---

        # Filtres d'application
        if (
            coti_id == "prevoyance_cadre" or coti_id == "apec"
        ) and contexte.statut_salarie != "Cadre":
            continue
        if coti_id == "prevoyance_non_cadre" and contexte.statut_salarie != "Non-Cadre":
            continue
        if coti_id == "mutuelle":
            continue  # Géré manuellement plus bas

        libelle = coti_data.get("libelle", "")
        base_id = coti_data.get("base", "brut")
        assiette = assiettes.get(
            base_id,
            assiettes["brut_plafonne"]
            if base_id == "plafond_ss"
            else assiettes["brut"],
        )

        taux_salarial = coti_data.get("salarial")
        taux_patronal_brut = coti_data.get("patronal")
        taux_patronal_final = taux_patronal_brut

        if isinstance(taux_patronal_brut, dict):
            if coti_id == "fnal":
                taux_patronal_final = (
                    taux_patronal_brut.get("taux_moins_50")
                    if contexte.effectif < 50
                    else taux_patronal_brut.get("taux_50_et_plus")
                )
            elif coti_id == "CFP":
                taux_patronal_final = (
                    taux_patronal_brut.get("taux_moins_11")
                    if contexte.effectif < 11
                    else taux_patronal_brut.get("taux_11_et_plus")
                )
            elif coti_id in ["taxe_apprentissage", "taxe_apprentissage_solde"]:
                taux_patronal_final = (
                    taux_patronal_brut.get("taux_alsace_moselle")
                    if contexte.is_alsace_moselle
                    else taux_patronal_brut.get("taux_metropole")
                )
            else:
                taux_patronal_final = 0.0

        smic_mensuel = (
            contexte.baremes.get("smic", {}).get("cas_general", 0.0) * 35 * 52 / 12
        )
        if coti_id == "allocations_familiales":
            taux_patronal_final = (
                coti_data.get("patronal_reduit")
                if salaire_brut <= 3.5 * smic_mensuel
                else coti_data.get("patronal_plein")
            )

        elif coti_id == "securite_sociale_maladie":
            taux_patronal_final = (
                coti_data.get("patronal_reduit")
                if salaire_brut <= 2.5 * smic_mensuel
                else coti_data.get("patronal_plein")
            )
            if contexte.is_alsace_moselle:
                taux_salarial = coti_data.get("salarial_Alsace_Moselle", 0.0)

        elif coti_id == "at_mp":
            taux_patronal_final = (
                contexte.entreprise.get("parametres_paie", {})
                .get("taux_specifiques", {})
                .get("taux_at_mp", 0.0)
                / 100.0
            )

        if coti_id == "csg" and isinstance(taux_salarial, dict):
            taux_csg_deductible = taux_salarial.get("deductible", 0.0)
            taux_csg_non_deductible = taux_salarial.get("non_deductible", 0.0)
            taux_csg_total = taux_csg_deductible + taux_csg_non_deductible

            for ligne in [
                _calculer_une_ligne(
                    "CSG déductible",
                    assiettes["csg_crds_base_normale"],
                    taux_csg_deductible,
                    None,
                ),
                _calculer_une_ligne(
                    "CSG/CRDS non déductible",
                    assiettes["csg_crds_base_normale"],
                    taux_csg_non_deductible,
                    None,
                ),
                _calculer_une_ligne(
                    "CSG/CRDS sur HS non déductible",
                    assiettes["csg_crds_base_hs"],
                    taux_csg_total,
                    None,
                ),
            ]:
                if ligne:
                    bulletin_cotisations.append(ligne)
            continue

        if isinstance(taux_patronal_final, str):
            taux_patronal_final = 0.0

        ligne_calculee = _calculer_une_ligne(
            libelle, assiette, taux_salarial, taux_patronal_final
        )

        if ligne_calculee:
            bulletin_cotisations.append(ligne_calculee)

    # Ajout manuel des cotisations forfaitaires (mutuelle, etc.)
    mutuelle_spec = contexte.contrat.get("specificites_paie", {}).get("mutuelle", {})
    if not isinstance(mutuelle_spec, dict):
        mutuelle_spec = {}
    if mutuelle_spec.get("adhesion"):
        # Nouveau format : charger depuis company_mutuelle_types si mutuelle_type_ids présent
        mutuelle_type_ids = mutuelle_spec.get("mutuelle_type_ids", [])
        if mutuelle_type_ids:
            # Charger les formules depuis la base de données
            try:
                supabase_url = os.environ.get("SUPABASE_URL")
                supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
                if supabase_url and supabase_key:
                    supabase_client: Client = create_client(supabase_url, supabase_key)
                    mutuelles_response = (
                        supabase_client.table("company_mutuelle_types")
                        .select("*")
                        .in_("id", mutuelle_type_ids)
                        .eq("is_active", True)
                        .execute()
                    )

                    if mutuelles_response.data:
                        for mutuelle in mutuelles_response.data:
                            bulletin_cotisations.append(
                                {
                                    "libelle": mutuelle.get(
                                        "libelle", "Mutuelle Frais de Santé"
                                    ),
                                    "base": None,
                                    "taux_salarial": None,
                                    "montant_salarial": float(
                                        mutuelle.get("montant_salarial", 0.0)
                                    ),
                                    "taux_patronal": None,
                                    "montant_patronal": float(
                                        mutuelle.get("montant_patronal", 0.0)
                                    ),
                                }
                            )
                else:
                    print(
                        "WARN: Variables Supabase non configurées, impossible de charger les mutuelles depuis la BDD",
                        file=sys.stderr,
                    )
            except Exception as e:
                print(
                    f"ERREUR: Impossible de charger les mutuelles depuis la BDD: {e}",
                    file=sys.stderr,
                )
                # Fallback sur l'ancien format si erreur

        # Ancien format : lignes_specifiques (rétrocompatibilité)
        lignes_specifiques = mutuelle_spec.get("lignes_specifiques", [])
        for ligne in lignes_specifiques:
            bulletin_cotisations.append(
                {
                    "libelle": ligne.get("libelle", "Mutuelle Frais de Santé"),
                    "base": None,
                    "taux_salarial": None,
                    "montant_salarial": ligne.get("montant_salarial", 0.0),
                    "taux_patronal": None,
                    "montant_patronal": ligne.get("montant_patronal", 0.0),
                }
            )

    # --- 🔍 DEBUG PRÉVOYANCE: DÉBUT DE LA SECTION SPÉCIFIQUE ---
    print("\n--- 🔍 DEBUG PRÉVOYANCE ---", file=sys.stderr)
    prevoyance_spec = contexte.contrat.get("specificites_paie", {}).get(
        "prevoyance", {}
    )
    if not isinstance(prevoyance_spec, dict):
        prevoyance_spec = {}
    adhesion_prevoyance = prevoyance_spec.get("adhesion", False)
    print(f"  -> Statut du salarié: {contexte.statut_salarie}", file=sys.stderr)
    print(
        f"  -> Adhésion prévoyance détectée dans le contrat: {adhesion_prevoyance}",
        file=sys.stderr,
    )

    if adhesion_prevoyance and contexte.statut_salarie == "Cadre":
        print("  -> ✅ Branche CADRE sélectionnée.", file=sys.stderr)
        # Cas CADRE : on lit les lignes depuis le contrat.json
        lignes_specifiques = prevoyance_spec.get("lignes_specifiques", [])
        print(
            f"  -> Lignes spécifiques trouvées pour le cadre: {len(lignes_specifiques)}",
            file=sys.stderr,
        )
        for ligne in lignes_specifiques:
            base_id = ligne.get("base", "brut_plafonne")
            assiette = assiettes.get(base_id, 0.0)
            ligne_calculee = _calculer_une_ligne(
                ligne.get("libelle"),
                assiette,
                ligne.get("salarial"),
                ligne.get("patronal"),
            )
            if ligne_calculee:
                bulletin_cotisations.append(ligne_calculee)
                print(
                    f"    -> Ligne calculée (Cadre): {ligne_calculee}", file=sys.stderr
                )

                # --- AJOUT DE LA LOGIQUE FORFAIT SOCIAL ---
                taux_fs = ligne.get("forfait_social")
                if taux_fs and ligne_calculee.get("montant_patronal", 0) > 0:
                    montant_patronal_prev = ligne_calculee["montant_patronal"]
                    ligne_fs = _calculer_une_ligne(
                        f"Forfait social {taux_fs * 100:.0f}% sur prévoyance",
                        montant_patronal_prev,
                        None,  # Pas de taux salarial
                        taux_fs,
                    )
                    if ligne_fs:
                        bulletin_cotisations.append(ligne_fs)
                        print(
                            f"      -> Ligne Forfait Social ajoutée: {ligne_fs}",
                            file=sys.stderr,
                        )

    elif adhesion_prevoyance and contexte.statut_salarie == "Non-Cadre":
        print("  -> ✅ Branche NON-CADRE sélectionnée.", file=sys.stderr)
        # Cas NON-CADRE : on lit la règle standard depuis les barèmes (cotisations.json)
        coti_data = contexte.get_cotisation_by_id("prevoyance_non_cadre")
        if coti_data:
            print(
                f"  -> Règle 'prevoyance_non_cadre' trouvée dans les barèmes: {json.dumps(coti_data)}",
                file=sys.stderr,
            )
            assiette = assiettes.get(coti_data.get("base", "brut_plafonne"), 0.0)
            print(
                f"  -> Assiette de calcul utilisée: {assiette:.2f} €", file=sys.stderr
            )
            ligne_calculee = _calculer_une_ligne(
                coti_data.get("libelle"),
                assiette,
                coti_data.get("salarial"),
                coti_data.get("patronal"),
            )
            if ligne_calculee:
                bulletin_cotisations.append(ligne_calculee)
                print(
                    f"  -> ✅ Ligne calculée (Non-Cadre) et ajoutée: {ligne_calculee}",
                    file=sys.stderr,
                )
            else:
                print(
                    "  -> ❌ Ligne non-cadre non ajoutée (calcul a retourné None ou 0).",
                    file=sys.stderr,
                )
        else:
            print(
                "  -> ❌ Règle 'prevoyance_non_cadre' INTROUVABLE dans les barèmes (cotisations.json).",
                file=sys.stderr,
            )
    else:
        print(
            "  -> ❌ Aucune branche de calcul de prévoyance n'a été exécutée.",
            file=sys.stderr,
        )
    print("--- FIN DEBUG PRÉVOYANCE ---\n", file=sys.stderr)

    # Ajout de la réduction salariale sur les heures supplémentaires
    if remuneration_heures_supp > 0:
        taux_reduction = (
            contexte.baremes.get("heures_supp", {})
            .get("reduction_salariale", {})
            .get("taux_reduction", {})
            .get("plafond_legal", 0.0)
        )
        montant_reduction = round(-remuneration_heures_supp * taux_reduction, 2)
        bulletin_cotisations.append(
            {
                "libelle": "Réduction de cotisations sur heures sup.",
                "base": remuneration_heures_supp,
                "taux_salarial": -taux_reduction,
                "montant_salarial": montant_reduction,
                "taux_patronal": None,
                "montant_patronal": 0.0,
            }
        )

    # Ajout de la déduction forfaitaire patronale sur les heures supplémentaires
    regles_deduction = contexte.baremes.get("heures_supp", {}).get(
        "deduction_patronale", {}
    )
    if total_heures_supp > 0 and regles_deduction:
        montant_par_heure = 0.0
        for palier in regles_deduction.get("montants_forfaitaires", []):
            if (
                palier.get("effectif_min", 0)
                <= contexte.effectif
                <= palier.get("effectif_max", 19)
            ):
                montant_par_heure = palier.get("montant_par_heure_sup_eur", 0.0)
                break

        if montant_par_heure > 0:
            montant_deduction = round(-total_heures_supp * montant_par_heure, 2)
            bulletin_cotisations.append(
                {
                    "libelle": "Déduction forfaitaire heures suppl. pat.",
                    "base": total_heures_supp,
                    "taux_salarial": None,
                    "montant_salarial": 0.0,
                    "taux_patronal": None,
                    "montant_patronal": montant_deduction,
                }
            )

    total_cotisations_salariales = sum(
        ligne.get("montant_salarial", 0.0) or 0.0 for ligne in bulletin_cotisations
    )
    print("INFO: Calcul des cotisations terminé.", file=sys.stderr)
    return bulletin_cotisations, round(total_cotisations_salariales, 2)
