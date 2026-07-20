from app.core.logging import get_logger, log_payroll_debug

logger = get_logger("modules.payroll.engine.calcul_cotisations")
# moteur_paie/calcul_cotisations.py

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
from .cotisations_rubriques import enrichir_ligne_cotisation
from .baremes_loader import resoudre_taux_vm_pour_paie
from app.shared.domain.employment_rules import is_cadre

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


def _cumul_agirc_arrco_debut_mois(
    contexte: ContextePaie,
) -> Tuple[float, float, float]:
    """Cumuls ANNÉE CIVILE (reset au 1er janvier, UNIQUEMENT pour ces 3 clés —
    ne touche à aucun autre cumul existant) nécessaires à la régularisation
    progressive Agirc-Arrco de la tranche 2 : (cumul_brut, cumul_pss,
    cumul_tranche_2_déjà_appliquée), AVANT le mois courant.

    Principe (régularisation progressive Agirc-Arrco, cf. doctrine Agirc-Arrco
    sur le lissage des tranches en cas de rémunération variable) : chaque mois,
    la tranche 2 « correcte » est recalculée sur le CUMUL annuel (cumul brut vs
    cumul PMSS), puis on ne retient que la DIFFÉRENCE avec ce qui a déjà été
    appliqué les mois précédents. Un pic de rémunération suivi d'un mois plus
    bas peut donc légitimement produire une assiette tranche 2 NÉGATIVE un
    mois donné (régularisation à la baisse) — comportement confirmé sur les
    bulletins réels HIRARD/NOBLE (Lewis mai 2026 : ligne « E_V7 PREVOYANCE NON
    CADRE TU2 META » à base négative -220,31 €, et « Complémentaire Tranche 2 »
    à base négative -220,31 € également, cohérent avec un même mécanisme
    appliqué uniformément à toutes les cotisations assises sur la tranche 2).
    """
    mois = getattr(contexte, "month", None)
    if mois == 1:
        return 0.0, 0.0, 0.0
    cumuls_racine = getattr(contexte, "cumuls", None) or {}
    if not isinstance(cumuls_racine, dict):
        return 0.0, 0.0, 0.0
    cumuls = cumuls_racine.get("cumuls") or {}
    if not isinstance(cumuls, dict):
        return 0.0, 0.0, 0.0
    try:
        return (
            float(cumuls.get("cumul_brut_agirc_arrco", 0.0) or 0.0),
            float(cumuls.get("cumul_pss_agirc_arrco", 0.0) or 0.0),
            float(cumuls.get("cumul_tranche_2_appliquee", 0.0) or 0.0),
        )
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.0


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
    assiette_cet = 0.0
    # On utilise maintenant le pss_calcule (proratisé ou non)
    if salaire_brut > pss_calcule:
        # La CET (Contribution d'Équilibre Technique) suit sa propre logique
        # (assiette = brut plafonné à 8×PSS, PAS de régularisation progressive
        # tranche 1/tranche 2 — traitée séparément, comportement inchangé).
        assiette_cet = min(salaire_brut, lc.FACTEUR_PLAFOND_TRANCHE_2 * pss_calcule)

    # --- Tranche 2 : régularisation progressive Agirc-Arrco (cumul annuel) ---
    # Remplace l'ancien calcul purement mensuel (assiette_tranche_2 = max(0,
    # min(brut, 8×PSS) - PSS)) par une régularisation sur le cumul de l'année
    # civile : la tranche 2 correcte est recalculée chaque mois sur le cumul
    # brut vs cumul PMSS, et seule la DIFFÉRENCE avec ce qui a déjà été
    # appliqué les mois précédents est retenue ce mois-ci — SANS jamais
    # plancher à zéro (peut être négative en cas de régularisation à la
    # baisse). Pour un salarié à rémunération stable, cette formule est
    # mathématiquement ÉQUIVALENTE à l'ancien calcul mensuel (linéarité),
    # donc sans risque de régression pour l'immense majorité des salariés ;
    # elle ne diverge que lorsque le cumul brut/PSS fluctue de façon non
    # proportionnelle d'un mois à l'autre (nouvel embauché en cours d'année,
    # mois à rémunération variable...).
    cumul_brut_avant, cumul_pss_avant, cumul_t2_applique_avant = (
        _cumul_agirc_arrco_debut_mois(contexte)
    )
    cumul_brut_incl = cumul_brut_avant + salaire_brut
    cumul_pss_incl = cumul_pss_avant + pss_calcule
    cumul_tranche_2_correct = max(
        0.0,
        min(cumul_brut_incl, lc.FACTEUR_PLAFOND_TRANCHE_2 * cumul_pss_incl)
        - cumul_pss_incl,
    )
    assiette_tranche_2 = round(cumul_tranche_2_correct - cumul_t2_applique_avant, 2)
    # Cumuls à jour (année civile), exposés via contexte pour persistance par
    # mettre_a_jour_cumuls (cf. payslip_run_common.py) — jamais un `if` sur un
    # salarié précis, s'applique uniformément à tous.
    try:
        contexte.agirc_arrco_cumuls_mois_courant = {
            "cumul_brut_agirc_arrco": round(cumul_brut_incl, 2),
            "cumul_pss_agirc_arrco": round(cumul_pss_incl, 2),
            "cumul_tranche_2_appliquee": round(
                cumul_t2_applique_avant + assiette_tranche_2, 2
            ),
        }
    except Exception:
        pass

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
                from app.core.database import supabase as supabase_client

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
        elif not is_cadre(contexte.statut_salarie):
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
        and is_cadre(contexte.statut_salarie)
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
        # Parts patronales entrant dans la base CSG SANS abattement frais pro
        # (elles ne sont pas de la rémunération). Exposées pour que le régime
        # apprenti reconstruise la même base sur sa fraction résiduelle.
        "csg_parts_patronales": round(
            part_patronale_prevoyance
            + part_patronale_retraite_sup
            + part_patronale_frais_sante,
            2,
        ),
    }


def _calculer_une_ligne(
    libelle: str,
    assiette: float,
    taux_salarial: float,
    taux_patronal: float,
    coti_id: Optional[str] = None,
    autoriser_assiette_negative: bool = False,
) -> Dict[str, Any] | None:
    # Garde-fou générique : on écarte les lignes à assiette nulle/négative,
    # SAUF quand l'appelant signale explicitement (via `autoriser_assiette_negative`)
    # qu'une assiette négative est légitime — cas de la régularisation progressive
    # Agirc-Arrco tranche 2 (le cumul annuel peut requalifier T1/T2 à la baisse
    # un mois donné, cf. HIRARD/NOBLE Lewis mai 2026). Généraliste : ne dépend
    # d'aucun salarié particulier, uniquement de la base de cotisation utilisée.
    if taux_salarial is None and taux_patronal is None:
        pass
    elif assiette < 0:
        if not autoriser_assiette_negative:
            return None
    elif assiette == 0:
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
        if coti_id == "apec":
            # APEC réservée aux cadres au sens AGIRC (statut catégoriel DSN) : un
            # salarié « Cadre » en paie mais déclaré « Non-Cadre » en DSN (forfait-
            # jour non-cadre CCN plasturgie, cf. GAILLET/BLONDEAU/GILLET/DROZ MBC
            # mai 2026) n'y est pas assujetti, même si son statut de paie sert de
            # base au calcul du brut forfait.
            cat_dsn = (contexte.statut_categoriel_dsn or "").strip().lower()
            if ("non" in cat_dsn and "cadre" in cat_dsn) or not is_cadre(
                contexte.statut_salarie
            ):
                continue
        elif coti_id == "prevoyance_cadre" and not is_cadre(contexte.statut_salarie):
            continue
        if coti_id == "prevoyance_non_cadre" and is_cadre(contexte.statut_salarie):
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
                # Régime récent : CSG/CRDS sur la seule fraction au-delà du
                # plafond, mais construite comme le droit commun — abattement
                # frais pro sur la rémunération, puis ajout des parts patronales
                # prévoyance/frais santé (non abattues), et isolement de la
                # quote-part d'heures sup. (CSG intégralement non déductible).
                # La quote-part d'HS résiduelle suit la même proratisation que
                # la réduction salariale HS (cf. plus bas) : les HS sont réputées
                # réparties uniformément entre fraction exonérée et fraction due.
                residuel = assiette_residuelle(
                    brut_cotisable, exo_apprenti["plafond"]
                )
                part_remuneration = 1.0 - exo_apprenti["abattement_csg"]
                residuel_hs = (
                    round(remuneration_heures_supp * residuel / brut_cotisable, 2)
                    if brut_cotisable > 0
                    else 0.0
                )
                base_csg_apprenti = round(
                    (residuel - residuel_hs) * part_remuneration
                    + assiettes["csg_parts_patronales"],
                    2,
                )
                base_csg_apprenti_hs = round(residuel_hs * part_remuneration, 2)
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
                    _calculer_une_ligne(
                        "CSG/CRDS sur HS non déductible",
                        base_csg_apprenti_hs,
                        taux_csg_total,
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
            libelle,
            assiette,
            taux_salarial,
            taux_patronal_final,
            coti_id=coti_id,
            # Base "tranche_2" : régularisation progressive Agirc-Arrco, cf.
            # `_cumul_agirc_arrco_debut_mois` — l'assiette peut légitimement
            # devenir négative (jamais plafonnée à 0) un mois donné.
            autoriser_assiette_negative=(base_id == "tranche_2"),
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
                from app.core.database import supabase as supabase_client

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

    if adhesion_prevoyance and is_cadre(contexte.statut_salarie):
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

    elif adhesion_prevoyance and not is_cadre(contexte.statut_salarie):
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
    if retraite_sup_spec.get("adhesion") and is_cadre(contexte.statut_salarie):
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
        # Apprenti : la fraction de rémunération <= plafond est déjà exonérée de
        # TOUTES les cotisations salariales, donc aucune cotisation n'est due sur
        # la quote-part d'heures sup. qu'elle contient. La réduction ne porte que
        # sur la part excédant le plafond, à proportion des HS dans le brut
        # (BOSS-Exo.HS / Urssaf : réduction limitée aux cotisations effectivement
        # dues). Vaut pour les deux régimes (79 % et 50 % du SMIC).
        base_reduction = remuneration_heures_supp
        if exo_apprenti is not None and brut_cotisable > 0:
            base_reduction = round(
                remuneration_heures_supp
                * assiette_residuelle(brut_cotisable, exo_apprenti["plafond"])
                / brut_cotisable,
                2,
            )
        montant_reduction_theorique = round(base_reduction * taux_reduction, 2)
        # Plafond légal MENSUEL (BOSS-Exo.HS-40, URSSAF) : la réduction ne peut
        # jamais excéder les cotisations salariales réellement dues par le
        # salarié sur la période — ce n'est PAS un plafond annuel cumulé (à ne
        # pas confondre avec le plafond fiscal IR de 7 500 €, mécanisme distinct).
        # On plafonne donc au total des cotisations salariales déjà calculées
        # à ce stade (toutes les lignes précédentes, exonérations incluses).
        cotisations_salariales_dues = round(
            sum(
                ligne.get("montant_salarial", 0.0) or 0.0
                for ligne in bulletin_cotisations
            ),
            2,
        )
        montant_reduction_plafonne = min(
            montant_reduction_theorique, max(cotisations_salariales_dues, 0.0)
        )
        montant_reduction = round(-montant_reduction_plafonne, 2)
        taux_salarial_effectif = (
            round(montant_reduction / base_reduction, 6)
            if base_reduction
            else -taux_reduction
        )
        bulletin_cotisations.append(
            enrichir_ligne_cotisation(
                {
                    "libelle": "Réduction de cotisations sur heures sup.",
                    "base": base_reduction,
                    "taux_salarial": taux_salarial_effectif,
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
