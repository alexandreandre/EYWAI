from app.core.logging import get_logger, log_payroll_debug

logger = get_logger("modules.payroll.engine.calcul_cotisations")
# moteur_paie/calcul_cotisations.py

import os
from .contexte import ContextePaie
from . import legal_constants as lc
from .exoneration_alternance import (
    assiette_residuelle,
    contexte_exoneration_apprenti,
    controle_salaire_minimum_alternant,
    exonerations_patronales_professionnalisation,
)
from .exoneration_stage import (
    assiette_stage_residuelle,
    contexte_exoneration_stage,
)
from typing import Dict, Any, List, Tuple, Optional
import json
from supabase import create_client, Client
from .cotisations_rubriques import enrichir_ligne_cotisation
from .baremes_loader import resoudre_taux_vm_pour_paie

# Fichier : moteur_paie/calcul_cotisations.py


def _assiette_pour_base(
    base_id: str,
    *,
    salaire_brut: float,
    brut_plafonne: float,
    tranche_2: float,
) -> float:
    if base_id == "tranche_2":
        return tranche_2
    if base_id in ("brut_plafonne", "plafond_ss"):
        return brut_plafonne
    return salaire_brut


def _sommer_part_patronale_lignes_taux(
    lignes: List[Dict[str, Any]],
    *,
    salaire_brut: float,
    brut_plafonne: float,
    tranche_2: float,
) -> float:
    total = 0.0
    for ligne in lignes:
        base_id = ligne.get("base", "brut_plafonne")
        assiette = _assiette_pour_base(
            base_id,
            salaire_brut=salaire_brut,
            brut_plafonne=brut_plafonne,
            tranche_2=tranche_2,
        )
        total += assiette * (ligne.get("patronal", 0.0) or 0.0)
    return total


def _calculer_assiettes(
    contexte: ContextePaie, salaire_brut: float, remuneration_heures_supp: float
) -> Dict[str, float]:
    """Prépare toutes les bases de calcul (assiettes) nécessaires pour les cotisations."""
    pss_mensuel = contexte.baremes.get("pss", {}).get("mensuel", 0.0)
    duree_legale_hebdo = lc.DUREE_LEGALE_HEBDO

    # --- NOUVEAU BLOC : CALCUL DU PLAFOND AU PRORATA ---
    pss_calcule = pss_mensuel
    duree_contrat_hebdo = contexte.duree_hebdo_contrat
    proratiser = (
        contexte.contrat.get("contrat", {})
        .get("temps_travail", {})
        .get("proratiser_plafond_ss", False)
    )

    if proratiser and duree_contrat_hebdo < duree_legale_hebdo:
        # Formule URSSAF : Plafond × (Durée retenue / Durée légale).
        # Les heures complémentaires du mois relèvent la durée retenue
        # (plafonnée à la durée légale) : on les convertit en heures mensuelles.
        heures_contrat_mois = round((duree_contrat_hebdo * 52) / 12, 2)
        heures_legales_mois = round((duree_legale_hebdo * 52) / 12, 2)
        heures_comp_mois = float(
            getattr(contexte, "heures_complementaires_mois", 0.0) or 0.0
        )
        ratio = (
            min(
                1.0,
                (heures_contrat_mois + heures_comp_mois) / heures_legales_mois,
            )
            if heures_legales_mois > 0
            else 1.0
        )
        pss_calcule = pss_mensuel * ratio
        log_payroll_debug(logger, f'INFO: Plafond SS proratisé pour temps partiel (HC {heures_comp_mois}h) : {pss_calcule:.2f} €')
    # --- FIN DU NOUVEAU BLOC ---

    # Assiettes conditionnelles
    assiette_tranche_2 = 0.0
    assiette_cet = 0.0
    # On utilise maintenant le pss_calcule (proratisé ou non)
    if salaire_brut > pss_calcule:
        assiette_tranche_2 = max(0, min(salaire_brut, lc.FACTEUR_PLAFOND_TRANCHE_2 * pss_calcule) - pss_calcule)
        assiette_cet = min(salaire_brut, lc.FACTEUR_PLAFOND_TRANCHE_2 * pss_calcule)

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
                logger.warning(f'WARN: Impossible de charger les mutuelles pour CSG: {e}')

        # Ancien format : lignes_specifiques (rétrocompatibilité)
        for ligne in mutuelle_spec.get("lignes_specifiques", []):
            # On ajoute la part patronale seulement si la ligne est marquée comme soumise à CSG
            if ligne.get(
                "part_patronale_soumise_a_csg", True
            ):  # True par défaut pour la compatibilité
                part_patronale_frais_sante += ligne.get("montant_patronal", 0.0) or 0.0

        # Fallback : montants inline sur mutuelle (sans mutuelle_type_ids ni lignes_specifiques)
        if (
            not mutuelle_type_ids
            and not mutuelle_spec.get("lignes_specifiques")
            and mutuelle_spec.get("montant_patronal") is not None
        ):
            if mutuelle_spec.get("part_patronale_soumise_a_csg", True):
                part_patronale_frais_sante += float(
                    mutuelle_spec.get("montant_patronal", 0.0) or 0.0
                )

    brut_plafonne = min(salaire_brut, pss_calcule)

    part_patronale_prevoyance = 0.0
    prevoyance_spec = contexte.contrat.get("specificites_paie", {}).get(
        "prevoyance", {}
    )
    if isinstance(prevoyance_spec, dict) and prevoyance_spec.get("adhesion"):
        lignes_prev = prevoyance_spec.get("lignes_specifiques", [])
        if lignes_prev:
            part_patronale_prevoyance = _sommer_part_patronale_lignes_taux(
                lignes_prev,
                salaire_brut=salaire_brut,
                brut_plafonne=brut_plafonne,
                tranche_2=assiette_tranche_2,
            )
        elif contexte.statut_salarie == "Non-Cadre":
            cotisation_prevoyance = contexte.get_cotisation_by_id(
                "prevoyance_non_cadre"
            )
            if cotisation_prevoyance and cotisation_prevoyance.get("patronal"):
                part_patronale_prevoyance = brut_plafonne * cotisation_prevoyance[
                    "patronal"
                ]

    part_patronale_retraite_sup = 0.0
    retraite_sup_spec = contexte.contrat.get("specificites_paie", {}).get(
        "retraite_sup", {}
    )
    if (
        isinstance(retraite_sup_spec, dict)
        and retraite_sup_spec.get("adhesion")
        and contexte.statut_salarie == "Cadre"
    ):
        part_patronale_retraite_sup = _sommer_part_patronale_lignes_taux(
            retraite_sup_spec.get("lignes_specifiques", []),
            salaire_brut=salaire_brut,
            brut_plafonne=brut_plafonne,
            tranche_2=assiette_tranche_2,
        )

    # CALCUL ASSIETTE CSG (inchangé)
    salaire_brut_hors_hs = salaire_brut - remuneration_heures_supp
    base_csg_normale = (
        (salaire_brut_hors_hs * 0.9825)
        + part_patronale_prevoyance
        + part_patronale_retraite_sup
        + part_patronale_frais_sante
    )
    base_csg_hs = remuneration_heures_supp * 0.9825

    return {
        "brut": salaire_brut,
        "plafond_ss": round(
            pss_calcule, 2
        ),  # On retourne le plafond potentiellement réduit
        "brut_plafonne": brut_plafonne,
        "tranche_2": round(assiette_tranche_2, 2),
        "assiette_cet": round(assiette_cet, 2),
        "csg_crds_base_normale": round(base_csg_normale, 2),
        "csg_crds_base_hs": round(base_csg_hs, 2),
    }


def _calculer_une_ligne(
    libelle: str,
    assiette: float,
    taux_salarial: float,
    taux_patronal: float,
    coti_id: Optional[str] = None,
) -> Dict[str, Any] | None:
    if assiette <= 0 and not (taux_salarial is None and taux_patronal is None):
        return None
    montant_salarial = round(assiette * (taux_salarial or 0.0), 2)
    montant_patronal = round(assiette * (taux_patronal or 0.0), 2)
    if montant_salarial == 0 and montant_patronal == 0:
        return None
    return enrichir_ligne_cotisation(
        {
            "libelle": libelle,
            "base": assiette,
            "taux_salarial": taux_salarial,
            "montant_salarial": montant_salarial,
            "taux_patronal": taux_patronal,
            "montant_patronal": montant_patronal,
        },
        coti_id=coti_id,
    )


def calculer_cotisations(
    contexte: ContextePaie,
    salaire_brut: float,
    remuneration_heures_supp: float = 0.0,
    total_heures_supp: float = 0.0,
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Calcule toutes les cotisations sociales, salariales et patronales.
    """
    log_payroll_debug(logger, 'INFO: Démarrage du calcul des cotisations...')

    heures_mois_ref = (contexte.duree_hebdo_contrat * 52) / 12
    exo_stage = contexte_exoneration_stage(contexte, heures_mois_ref)
    brut_cotisable = salaire_brut
    ligne_exo_stage = None

    if exo_stage is not None:
        plafond_stage = exo_stage["plafond"]
        if salaire_brut <= plafond_stage + 0.01:
            return [
                enrichir_ligne_cotisation(
                    {
                        "libelle": "Gratification de stage exonérée",
                        "base": round(salaire_brut, 2),
                        "taux_salarial": None,
                        "montant_salarial": 0.0,
                        "taux_patronal": None,
                        "montant_patronal": 0.0,
                    },
                    coti_id="exoneration_stage",
                )
            ], 0.0
        part_exo = round(min(salaire_brut, plafond_stage), 2)
        ligne_exo_stage = enrichir_ligne_cotisation(
            {
                "libelle": "Gratification de stage exonérée",
                "base": part_exo,
                "taux_salarial": None,
                "montant_salarial": 0.0,
                "taux_patronal": None,
                "montant_patronal": 0.0,
            },
            coti_id="exoneration_stage",
        )
        brut_cotisable = assiette_stage_residuelle(salaire_brut, plafond_stage)

    assiettes = _calculer_assiettes(contexte, brut_cotisable, remuneration_heures_supp)
    root_key = next(
        (k for k, v in contexte.baremes["cotisations"].items() if isinstance(v, list)),
        "cotisations",
    )
    liste_cotisations_brutes = contexte.baremes["cotisations"].get(root_key, [])
    bulletin_cotisations = []

    # Exonération apprenti (None si non applicable). Tout est dynamique (barèmes).
    exo_apprenti = contexte_exoneration_apprenti(contexte)
    exoneration_salariale_apprenti = 0.0

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

        # Mandataire social assimilé salarié : exclu de l'assurance chômage et de
        # l'AGS. Liste surchargeable via payroll_config.mandataire.cotisations_exclues.
        if contexte.is_mandataire:
            cfg_mandataire = contexte.baremes.get("mandataire", {}) or {}
            cotis_exclues = cfg_mandataire.get(
                "cotisations_exclues",
                ["assurance_chomage", "ags", "chomage", "apec"],
            )
            if coti_id in cotis_exclues:
                continue

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
                    if contexte.effectif < lc.SEUIL_EFFECTIF_FNAL
                    else taux_patronal_brut.get("taux_50_et_plus")
                )
            elif coti_id == "CFP":
                taux_patronal_final = (
                    taux_patronal_brut.get("taux_moins_11")
                    if contexte.effectif < lc.SEUIL_EFFECTIF_CFP
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

        # SMIC mensuel TEMPS PLEIN (non proratisé) — seuils légaux maladie/AF.
        # Centralisé sur le contexte (DRY) sans changer le comportement existant.
        smic_mensuel = contexte.smic_mensuel
        # Bandeaux maladie/AF : supprimés à partir de 2026 (absorbés par la RGDU,
        # cf. legal_constants.ANNEE_BASCULE_RGDU). Avant 2026 : taux réduit sous seuil.
        annee_paie = getattr(contexte, "year", None) or lc.ANNEE_BASCULE_RGDU
        bandeaux_supprimes = annee_paie >= lc.ANNEE_BASCULE_RGDU
        if coti_id == "allocations_familiales":
            taux_patronal_final = (
                coti_data.get("patronal_plein")
                if bandeaux_supprimes or brut_cotisable > 3.5 * smic_mensuel
                else coti_data.get("patronal_reduit")
            )

        elif coti_id == "securite_sociale_maladie":
            taux_patronal_final = (
                coti_data.get("patronal_plein")
                if bandeaux_supprimes or brut_cotisable > 2.5 * smic_mensuel
                else coti_data.get("patronal_reduit")
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

        elif coti_id == "versement_mobilite":
            taux_patronal_final = resoudre_taux_vm_pour_paie(
                contexte.baremes,
                contexte.entreprise,
                alertes=contexte.alertes_baremes,
            )
            if taux_patronal_final is None:
                continue

        if coti_id == "csg" and isinstance(taux_salarial, dict):
            taux_csg_deductible = taux_salarial.get("deductible", 0.0)
            taux_csg_non_deductible = taux_salarial.get("non_deductible", 0.0)
            taux_csg_total = taux_csg_deductible + taux_csg_non_deductible

            # --- Cas apprenti : base CSG/CRDS ISOLÉE (pas de parts patronales) ---
            if exo_apprenti is not None:
                if not exo_apprenti["csg_crds_assujettie"]:
                    # Régime ancien : apprenti totalement exonéré de CSG/CRDS.
                    continue
                # Régime récent : CSG/CRDS sur la fraction au-delà du plafond,
                # après abattement frais pro. Sans parts patronales mutuelle/prévoyance.
                base_csg_apprenti = round(
                    assiette_residuelle(brut_cotisable, exo_apprenti["plafond"])
                    * (1.0 - exo_apprenti["abattement_csg"]),
                    2,
                )
                for ligne in [
                    _calculer_une_ligne(
                        "CSG déductible",
                        base_csg_apprenti,
                        taux_csg_deductible,
                        None,
                        coti_id="csg_deductible",
                    ),
                    _calculer_une_ligne(
                        "CSG/CRDS non déductible",
                        base_csg_apprenti,
                        taux_csg_non_deductible,
                        None,
                        coti_id="csg_non_deductible",
                    ),
                ]:
                    if ligne:
                        bulletin_cotisations.append(ligne)
                continue

            for ligne in [
                _calculer_une_ligne(
                    "CSG déductible",
                    assiettes["csg_crds_base_normale"],
                    taux_csg_deductible,
                    None,
                    coti_id="csg_deductible",
                ),
                _calculer_une_ligne(
                    "CSG/CRDS non déductible",
                    assiettes["csg_crds_base_normale"],
                    taux_csg_non_deductible,
                    None,
                    coti_id="csg_non_deductible",
                ),
                _calculer_une_ligne(
                    "CSG/CRDS sur HS non déductible",
                    assiettes["csg_crds_base_hs"],
                    taux_csg_total,
                    None,
                    coti_id="csg_non_deductible",
                ),
            ]:
                if ligne:
                    bulletin_cotisations.append(ligne)
            continue

        if isinstance(taux_patronal_final, str):
            taux_patronal_final = 0.0

        ligne_calculee = _calculer_une_ligne(
            libelle, assiette, taux_salarial, taux_patronal_final, coti_id=coti_id
        )

        if ligne_calculee:
            bulletin_cotisations.append(ligne_calculee)

        # --- Exonération salariale apprenti (cotisations légales/conv. non exclues) ---
        # On accumule la part salariale calculée sur la fraction <= plafond.
        # Mutuelle/prévoyance/APEC restent dues (listées dans cotisations_exclues).
        if (
            exo_apprenti is not None
            and taux_salarial
            and not isinstance(taux_salarial, dict)
            and coti_id not in exo_apprenti["cotisations_exclues"]
            and coti_id
            not in ("csg", "csg_deductible", "csg_non_deductible", "crds")
        ):
            base_exoneree = min(assiette, exo_apprenti["plafond"])
            exoneration_salariale_apprenti += round(
                taux_salarial * base_exoneree, 2
            )

    # Contrat de professionnalisation : exonérations patronales éventuelles
    # (vides par défaut — la réduction générale couvre déjà l'historique).
    for ligne_pro in exonerations_patronales_professionnalisation(
        contexte, salaire_brut
    ):
        bulletin_cotisations.append(enrichir_ligne_cotisation(ligne_pro))

    # Contrôle (non bloquant) du salaire minimum conventionnel alternant.
    alerte_salaire = controle_salaire_minimum_alternant(contexte, salaire_brut)
    if alerte_salaire is not None and isinstance(contexte.alertes_baremes, list):
        contexte.alertes_baremes.append(alerte_salaire)

    # Ligne d'allègement visible : exonération des cotisations salariales apprenti.
    if exo_apprenti is not None and exoneration_salariale_apprenti > 0:
        bulletin_cotisations.append(
            enrichir_ligne_cotisation(
                {
                    "libelle": "Exonération cotisations salariales apprenti",
                    "base": round(min(salaire_brut, exo_apprenti["plafond"]), 2),
                    "taux_salarial": None,
                    "montant_salarial": -round(exoneration_salariale_apprenti, 2),
                    "taux_patronal": None,
                    "montant_patronal": 0.0,
                },
                coti_id="exoneration_apprenti_salariale",
            )
        )

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
                                enrichir_ligne_cotisation(
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
                                    },
                                    coti_id="mutuelle",
                                )
                            )
                else:
                    logger.warning('WARN: Variables Supabase non configurées, impossible de charger les mutuelles depuis la BDD')
            except Exception as e:
                logger.warning(f'ERREUR: Impossible de charger les mutuelles depuis la BDD: {e}')
                # Fallback sur l'ancien format si erreur

        # Ancien format : lignes_specifiques (rétrocompatibilité)
        lignes_specifiques = mutuelle_spec.get("lignes_specifiques", [])
        for ligne in lignes_specifiques:
            bulletin_cotisations.append(
                enrichir_ligne_cotisation(
                    {
                        "libelle": ligne.get("libelle", "Mutuelle Frais de Santé"),
                        "base": None,
                        "taux_salarial": None,
                        "montant_salarial": ligne.get("montant_salarial", 0.0),
                        "taux_patronal": None,
                        "montant_patronal": ligne.get("montant_patronal", 0.0),
                    },
                    coti_id="mutuelle",
                )
            )

        # Fallback montants inline (sans mutuelle_type_ids ni lignes_specifiques)
        if (
            not mutuelle_type_ids
            and not lignes_specifiques
            and (
                mutuelle_spec.get("montant_salarial") is not None
                or mutuelle_spec.get("montant_patronal") is not None
            )
        ):
            bulletin_cotisations.append(
                enrichir_ligne_cotisation(
                    {
                        "libelle": mutuelle_spec.get("libelle", "Mutuelle Frais de Santé"),
                        "base": None,
                        "taux_salarial": None,
                        "montant_salarial": float(
                            mutuelle_spec.get("montant_salarial", 0.0) or 0.0
                        ),
                        "taux_patronal": None,
                        "montant_patronal": float(
                            mutuelle_spec.get("montant_patronal", 0.0) or 0.0
                        ),
                    },
                    coti_id="mutuelle",
                )
            )

    if ligne_exo_stage is not None:
        bulletin_cotisations.insert(0, ligne_exo_stage)
    log_payroll_debug(logger, '\n--- 🔍 DEBUG PRÉVOYANCE ---')
    prevoyance_spec = contexte.contrat.get("specificites_paie", {}).get(
        "prevoyance", {}
    )
    if not isinstance(prevoyance_spec, dict):
        prevoyance_spec = {}
    adhesion_prevoyance = prevoyance_spec.get("adhesion", False)
    log_payroll_debug(logger, f'  -> Statut du salarié: {contexte.statut_salarie}')
    log_payroll_debug(logger, f'  -> Adhésion prévoyance détectée dans le contrat: {adhesion_prevoyance}')

    if adhesion_prevoyance and contexte.statut_salarie == "Cadre":
        logger.info('  -> ✅ Branche CADRE sélectionnée.')
        # Cas CADRE : on lit les lignes depuis le contrat.json
        lignes_specifiques = prevoyance_spec.get("lignes_specifiques", [])
        log_payroll_debug(logger, f'  -> Lignes spécifiques trouvées pour le cadre: {len(lignes_specifiques)}')
        for ligne in lignes_specifiques:
            base_id = ligne.get("base", "brut_plafonne")
            assiette = assiettes.get(base_id, 0.0)
            ligne_calculee = _calculer_une_ligne(
                ligne.get("libelle"),
                assiette,
                ligne.get("salarial"),
                ligne.get("patronal"),
                coti_id="prevoyance_cadre",
            )
            if ligne_calculee:
                bulletin_cotisations.append(ligne_calculee)
                log_payroll_debug(logger, f'    -> Ligne calculée (Cadre): {ligne_calculee}')

                # --- AJOUT DE LA LOGIQUE FORFAIT SOCIAL ---
                taux_fs = ligne.get("forfait_social")
                if taux_fs and ligne_calculee.get("montant_patronal", 0) > 0:
                    montant_patronal_prev = ligne_calculee["montant_patronal"]
                    ligne_fs = _calculer_une_ligne(
                        f"Forfait social {taux_fs * 100:.0f}% sur prévoyance",
                        montant_patronal_prev,
                        None,
                        taux_fs,
                        coti_id="forfait_social",
                    )
                    if ligne_fs:
                        bulletin_cotisations.append(ligne_fs)
                        log_payroll_debug(logger, f'      -> Ligne Forfait Social ajoutée: {ligne_fs}')

    elif adhesion_prevoyance and contexte.statut_salarie == "Non-Cadre":
        logger.info('  -> ✅ Branche NON-CADRE sélectionnée.')
        lignes_specifiques = prevoyance_spec.get("lignes_specifiques", [])
        if lignes_specifiques:
            log_payroll_debug(
                logger,
                f'  -> Lignes spécifiques non-cadre: {len(lignes_specifiques)}',
            )
            for ligne in lignes_specifiques:
                base_id = ligne.get("base", "brut_plafonne")
                assiette = assiettes.get(base_id, 0.0)
                ligne_calculee = _calculer_une_ligne(
                    ligne.get("libelle"),
                    assiette,
                    ligne.get("salarial"),
                    ligne.get("patronal"),
                    coti_id="prevoyance_non_cadre",
                )
                if ligne_calculee:
                    bulletin_cotisations.append(ligne_calculee)
        else:
            coti_data = contexte.get_cotisation_by_id("prevoyance_non_cadre")
            if coti_data:
                log_payroll_debug(
                    logger,
                    f"  -> Règle 'prevoyance_non_cadre' barème global: {json.dumps(coti_data)}",
                )
                assiette = assiettes.get(coti_data.get("base", "brut_plafonne"), 0.0)
                ligne_calculee = _calculer_une_ligne(
                    coti_data.get("libelle"),
                    assiette,
                    coti_data.get("salarial"),
                    coti_data.get("patronal"),
                    coti_id="prevoyance_non_cadre",
                )
                if ligne_calculee:
                    bulletin_cotisations.append(ligne_calculee)
            else:
                logger.warning(
                    "  -> ❌ Règle 'prevoyance_non_cadre' INTROUVABLE dans les barèmes."
                )
    else:
        logger.warning("  -> ❌ Aucune branche de calcul de prévoyance n'a été exécutée.")
    log_payroll_debug(logger, '--- FIN DEBUG PRÉVOYANCE ---\n')

    retraite_sup_spec = contexte.contrat.get("specificites_paie", {}).get(
        "retraite_sup", {}
    )
    if not isinstance(retraite_sup_spec, dict):
        retraite_sup_spec = {}
    if retraite_sup_spec.get("adhesion") and contexte.statut_salarie == "Cadre":
        for ligne in retraite_sup_spec.get("lignes_specifiques", []):
            base_id = ligne.get("base", "brut_plafonne")
            assiette = assiettes.get(base_id, 0.0)
            ligne_calculee = _calculer_une_ligne(
                ligne.get("libelle"),
                assiette,
                ligne.get("salarial"),
                ligne.get("patronal"),
                coti_id="retraite_sup",
            )
            if ligne_calculee:
                bulletin_cotisations.append(ligne_calculee)

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
            enrichir_ligne_cotisation(
                {
                    "libelle": "Réduction de cotisations sur heures sup.",
                    "base": remuneration_heures_supp,
                    "taux_salarial": -taux_reduction,
                    "montant_salarial": montant_reduction,
                    "taux_patronal": None,
                    "montant_patronal": 0.0,
                },
                coti_id="reduction_hs_salariale",
            )
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
                enrichir_ligne_cotisation(
                    {
                        "libelle": "Déduction forfaitaire heures suppl. pat.",
                        "base": total_heures_supp,
                        "taux_salarial": None,
                        "montant_salarial": 0.0,
                        "taux_patronal": None,
                        "montant_patronal": montant_deduction,
                    },
                    coti_id="deduction_hs_patronale",
                )
            )

    total_cotisations_salariales = sum(
        ligne.get("montant_salarial", 0.0) or 0.0 for ligne in bulletin_cotisations
    )
    bulletin_cotisations = [
        enrichir_ligne_cotisation(ligne) for ligne in bulletin_cotisations
    ]
    logger.info('INFO: Calcul des cotisations terminé.')
    return bulletin_cotisations, round(total_cotisations_salariales, 2)
