"""
Module de simulation de bulletins de paie
Permet de créer des bulletins simulés avec pré-remplissage et personnalisation
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import copy

logger = logging.getLogger(__name__)


class SimulationError(Exception):
    """Exception levée en cas d'erreur dans la simulation"""
    pass


def preremplir_donnees_simulation(
    employee_data: Dict[str, Any],
    month: int,
    year: int,
    calendrier_reel: Optional[Dict[str, Any]] = None,
    saisies_reelles: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Pré-remplit les données de simulation à partir d'un bulletin réel ou de données par défaut

    Args:
        employee_data: Données employé
        month: Mois de simulation
        year: Année de simulation
        calendrier_reel: Calendrier réel si disponible (pour pré-remplissage)
        saisies_reelles: Saisies réelles si disponibles

    Returns:
        Dict contenant les données pré-remplies pour la simulation
    """
    logger.info(f"Pré-remplissage données simulation pour {month}/{year}")

    # Données par défaut du contrat
    duree_hebdo = employee_data.get("duree_hebdomadaire", 35.0)
    salaire_base = employee_data.get("salaire_base", 0.0)

    # Calculer les heures théoriques du mois (environ 4.33 semaines par mois)
    heures_theoriques = (duree_hebdo * 52) / 12

    donnees_prefill = {
        "employee_data": {
            "employee_id": employee_data.get("id"),
            "nom_complet": f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}",
            "statut": employee_data.get("statut", "Non-cadre"),
            "salaire_base": salaire_base,
            "duree_hebdomadaire": duree_hebdo
        },
        "periode": {
            "month": month,
            "year": year,
            "heures_theoriques": round(heures_theoriques, 2)
        },
        "calendrier": {},
        "saisies": {
            "primes": [],
            "absences": [],
            "conges": []
        }
    }

    # Pré-remplir depuis le calendrier réel si disponible
    if calendrier_reel:
        donnees_prefill["calendrier"] = copy.deepcopy(calendrier_reel)
        logger.info("Calendrier réel chargé pour pré-remplissage")
    else:
        # Calendrier par défaut : mois complet travaillé
        donnees_prefill["calendrier"] = {
            "planned_calendar": {
                "heures_prevues": heures_theoriques,
                "evenements": []
            },
            "actual_hours": {
                "heures_reelles": heures_theoriques,
                "evenements": []
            }
        }

    # Pré-remplir depuis les saisies réelles si disponibles
    if saisies_reelles:
        donnees_prefill["saisies"] = copy.deepcopy(saisies_reelles)
        logger.info("Saisies réelles chargées pour pré-remplissage")

    return donnees_prefill


def creer_simulation_bulletin(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
    month: int,
    year: int,
    scenario_params: Dict[str, Any],
    prefill_from_real: bool = False,
    calendrier_reel: Optional[Dict[str, Any]] = None,
    saisies_reelles: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Crée un bulletin de paie simulé avec les paramètres du scénario

    Args:
        employee_data: Données employé (peut être minimal avec manual_params)
        company_data: Données entreprise
        baremes: Barèmes de cotisations
        month: Mois de simulation
        year: Année de simulation
        scenario_params: Paramètres du scénario de simulation
        prefill_from_real: Si True, pré-remplit depuis bulletin réel
        calendrier_reel: Calendrier réel (si prefill_from_real=True)
        saisies_reelles: Saisies réelles (si prefill_from_real=True)

    Returns:
        Dict contenant:
            - payslip_data: Bulletin de paie complet
            - scenario_applied: Paramètres du scénario appliqués
            - metadata: Métadonnées de la simulation

    Raises:
        SimulationError: Si les paramètres sont invalides
    """
    logger.info(f"Création simulation bulletin pour {month}/{year}")

    # Vérifier si on est en mode manuel (sans modèle d'employé réel)
    is_manual_mode = employee_data.get("id") == "manual"

    if is_manual_mode:
        # Mode simplifié : utiliser les taux réels de la base de données
        bulletin = _creer_bulletin_simplifie(
            employee_data,
            company_data,
            scenario_params,
            month,
            year,
            baremes
        )
    else:
        # Mode complet avec moteur de paie
        # Pré-remplissage si demandé
        if prefill_from_real:
            donnees_base = preremplir_donnees_simulation(
                employee_data,
                month,
                year,
                calendrier_reel,
                saisies_reelles
            )
            calendrier = donnees_base["calendrier"]
            saisies = donnees_base["saisies"]
        else:
            # Données vierges
            duree_hebdo = employee_data.get("duree_hebdomadaire", 35.0)
            heures_theoriques = (duree_hebdo * 52) / 12

            calendrier = {
                "planned_calendar": {
                    "heures_prevues": heures_theoriques,
                    "evenements": []
                },
                "actual_hours": {
                    "heures_reelles": heures_theoriques,
                    "evenements": []
                }
            }
            saisies = {
                "primes": [],
                "absences": [],
                "conges": []
            }

        # Appliquer les paramètres du scénario
        calendrier_simule, saisies_simulees = _appliquer_scenario(
            calendrier,
            saisies,
            scenario_params
        )

        # Gérer l'override du salaire de base si spécifié
        employee_data_simule = employee_data.copy()
        if "salaire_base_override" in scenario_params:
            employee_data_simule["salaire_base"] = scenario_params["salaire_base_override"]

        # Imports du moteur de paie (uniquement en mode complet)
        from .contexte import ChargerContexte
        from .bulletin import creer_bulletin_final

        # Charger le contexte
        contexte = ChargerContexte(employee_data_simule, company_data, baremes)

        # Calculer le bulletin
        try:
            bulletin = creer_bulletin_final(
                contexte,
                calendrier_simule,
                saisies_simulees
            )
        except Exception as e:
            logger.error(f"Erreur lors du calcul du bulletin simulé: {str(e)}")
            raise SimulationError(f"Erreur de calcul: {str(e)}")

    # Ajouter des métadonnées de simulation
    metadata = {
        "simulation_date": datetime.now().isoformat(),
        "month": month,
        "year": year,
        "prefilled_from_real": prefill_from_real if not is_manual_mode else False,
        "scenario_applied": scenario_params,
        "mode": "manual" if is_manual_mode else "complet"
    }

    return {
        "payslip_data": bulletin,
        "scenario_applied": scenario_params,
        "metadata": metadata
    }


def _creer_bulletin_simplifie(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    scenario_params: Dict[str, Any],
    month: int,
    year: int,
    baremes: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Crée un bulletin simplifié avec calcul utilisant les barèmes réels de la base de données

    Args:
        employee_data: Données employé minimales
        company_data: Données entreprise
        scenario_params: Paramètres du scénario
        month: Mois
        year: Année
        baremes: Barèmes chargés depuis la base de données

    Returns:
        Bulletin de paie simplifié avec taux réels
    """
    # Récupération des paramètres
    statut = employee_data.get("statut", "Non-cadre")
    taux_pas = employee_data.get("taux_prelevement_source", 0.0) / 100
    brut_force = scenario_params.get("salaire_base_override", employee_data.get("salaire_base", 0.0))

    # Récupérer les barèmes réels
    if not baremes:
        logger.warning("Barèmes non fournis, utilisation de taux approximatifs")
        # Fallback sur taux approximatifs
        if statut == "Cadre":
            taux_cotis_salarial = 0.23
            taux_cotis_patronal = 0.45
        else:
            taux_cotis_salarial = 0.22
            taux_cotis_patronal = 0.42

        total_cotis_salariales = brut_force * taux_cotis_salarial
        total_cotis_patronales = brut_force * taux_cotis_patronal
        cotisations_detaillees = []
    else:
        # Calculer avec les taux réels
        cotisations_detaillees, total_cotis_salariales, total_cotis_patronales = _calculer_cotisations_reelles(
            brut_force, statut, baremes, company_data
        )

    net_social = brut_force - total_cotis_salariales

    # CSG/CRDS sur une base de 98.25% du brut
    base_csg = brut_force * 0.9825

    # Récupérer les taux CSG/CRDS depuis les barèmes si disponibles
    taux_csg_deductible = 0.068
    taux_csg_non_deductible = 0.024
    taux_crds = 0.005

    if baremes:
        cotisations_list = _get_cotisations_list(baremes)
        for coti in cotisations_list:
            if coti.get('id') == 'csg':
                taux_salarial = coti.get('salarial', {})
                if isinstance(taux_salarial, dict):
                    taux_csg_deductible = taux_salarial.get('deductible', 0.068)
                    taux_csg_non_deductible = taux_salarial.get('non_deductible', 0.024)
            elif coti.get('id') == 'crds':
                taux_crds = coti.get('salarial', 0.005)

    csg_deductible = base_csg * taux_csg_deductible
    csg_non_deductible = base_csg * taux_csg_non_deductible
    crds = base_csg * taux_crds

    # Le net imposable = brut - cotisations salariales - CSG déductible
    net_imposable = brut_force - total_cotis_salariales - csg_deductible

    # PAS
    montant_pas = net_imposable * taux_pas

    # Net à payer = net imposable - PAS - CSG non déductible - CRDS
    net_a_payer = net_imposable - montant_pas - csg_non_deductible - crds

    cout_employeur = brut_force + total_cotis_patronales

    # Nom du mois en français
    mois_noms = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    periode_str = f"{mois_noms[month]} {year}"

    # Construire un bulletin détaillé compatible avec la structure attendue
    bulletin = {
        "en_tete": {
            "periode": periode_str,
            "entreprise": {
                "raison_sociale": company_data.get("identification", {}).get("raison_sociale", ""),
                "siret": company_data.get("identification", {}).get("siret", ""),
                "adresse": company_data.get("identification", {}).get("adresse", "")
            },
            "salarie": {
                "nom_complet": f"{employee_data.get('first_name', '')} {employee_data.get('last_name', '')}".strip() or "Simulation Manuelle",
                "nir": employee_data.get("nir", ""),
                "emploi": employee_data.get("emploi", ""),
                "statut": statut,
                "date_entree": employee_data.get("date_entree", "")
            }
        },
        "details_conges": [],
        "details_absences": [],
        "calcul_du_brut": [
            {
                "libelle": "Salaire de base (simulation)",
                "gain": round(brut_force, 2),
                "perte": None
            }
        ],
        "arbitrage_conges": None,
        "salaire_brut": round(brut_force, 2),
        "structure_cotisations": {
            "bloc_principales": cotisations_detaillees if cotisations_detaillees else [
                {
                    "libelle": "Cotisations sociales (estimation moyenne)",
                    "base": round(brut_force, 2),
                    "montant_salarial": round(total_cotis_salariales, 2),
                    "montant_patronal": round(total_cotis_patronales, 2)
                }
            ],
            "bloc_allegements": [],
            "bloc_autres_contributions": {"lignes": [], "total": 0.0},
            "total_avant_csg_crds": {
                "libelle": "Total des retenues",
                "montant_salarial": round(total_cotis_salariales, 2),
                "montant_patronal": round(total_cotis_patronales, 2)
            },
            "bloc_csg_non_deductible": [
                {
                    "libelle": "CSG déductible",
                    "base": round(base_csg, 2),
                    "taux_salarial": taux_csg_deductible,
                    "montant_salarial": round(csg_deductible, 2),
                    "montant_patronal": 0.0
                },
                {
                    "libelle": "CSG non déductible",
                    "base": round(base_csg, 2),
                    "taux_salarial": taux_csg_non_deductible,
                    "montant_salarial": round(csg_non_deductible, 2),
                    "montant_patronal": 0.0
                },
                {
                    "libelle": "CRDS",
                    "base": round(base_csg, 2),
                    "taux_salarial": taux_crds,
                    "montant_salarial": round(crds, 2),
                    "montant_patronal": 0.0
                }
            ],
            "total_salarial": round(total_cotis_salariales + csg_deductible + csg_non_deductible + crds, 2),
            "total_patronal": round(total_cotis_patronales, 2)
        },
        "synthese_net": {
            "net_social_avant_impot": round(net_social, 2),
            "net_imposable": round(net_imposable, 2),
            "impot_prelevement_a_la_source": {
                "base": round(net_imposable, 2),
                "taux": taux_pas * 100,
                "montant": round(montant_pas, 2)
            },
            "remboursement_transport": 0.0
        },
        "primes_non_soumises": [],
        "net_a_payer": round(net_a_payer, 2),
        "pied_de_page": {
            "cout_total_employeur": round(cout_employeur, 2),
            "cumuls_annuels": {
                "_commentaire": "Simulation manuelle - pas de cumuls",
                "brut_cumule": 0.0,
                "net_imposable_cumule": 0.0,
                "heures_supplementaires_cumulees": 0
            }
        }
    }

    return bulletin


def _get_cotisations_list(baremes: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrait la liste des cotisations depuis les barèmes

    Args:
        baremes: Barèmes chargés depuis la base

    Returns:
        Liste des cotisations
    """
    cotisations_data = baremes.get('cotisations', {})

    # Trouver la clé racine contenant la liste
    root_key = next((k for k, v in cotisations_data.items() if isinstance(v, list)), None)

    if root_key:
        return cotisations_data.get(root_key, [])
    elif isinstance(cotisations_data, list):
        return cotisations_data
    else:
        return []


def _calculer_cotisations_reelles(
    brut: float,
    statut: str,
    baremes: Dict[str, Any],
    company_data: Dict[str, Any]
) -> tuple[List[Dict[str, Any]], float, float]:
    """
    Calcule les cotisations réelles en utilisant les barèmes de la base de données

    Args:
        brut: Salaire brut
        statut: Statut du salarié (Cadre / Non-cadre)
        baremes: Barèmes chargés depuis la base
        company_data: Données entreprise

    Returns:
        Tuple (cotisations_detaillees, total_salarial, total_patronal)
    """
    cotisations_detaillees = []
    total_salarial = 0.0
    total_patronal = 0.0

    # Récupérer PSS et SMIC
    pss_mensuel = baremes.get('pss', {}).get('mensuel', 3864.0)  # Valeur 2025 par défaut
    smic_horaire = baremes.get('smic', {}).get('cas_general', 11.88)
    smic_mensuel = smic_horaire * 35 * 52 / 12

    # Calculer les assiettes
    brut_plafonne = min(brut, pss_mensuel)
    assiette_tranche_2 = max(0, min(brut, 8 * pss_mensuel) - pss_mensuel) if brut > pss_mensuel else 0.0

    # Récupérer l'effectif pour FNAL et CFP
    effectif = company_data.get('parametres_paie', {}).get('effectif', 0)

    # Récupérer le taux AT/MP
    taux_at_mp = company_data.get('parametres_paie', {}).get('taux_specifiques', {}).get('taux_at_mp', 0.0) / 100.0

    # Parcourir les cotisations
    cotisations_list = _get_cotisations_list(baremes)

    for coti in cotisations_list:
        coti_id = coti.get('id')
        libelle = coti.get('libelle', '')

        # Filtres d'application
        if coti_id in ['prevoyance_cadre', 'apec'] and statut != 'Cadre':
            continue
        if coti_id == 'prevoyance_non_cadre' and statut != 'Non-Cadre':
            continue
        if coti_id == 'mutuelle':
            continue  # Géré séparément dans le moteur complet

        # Déterminer l'assiette
        base_id = coti.get('base', 'brut')
        if base_id == 'plafond_ss':
            assiette = float(brut_plafonne)
        elif base_id == 'tranche_2':
            assiette = float(assiette_tranche_2)
        elif base_id == 'brut':
            assiette = float(brut)
        else:
            assiette = float(brut)

        if assiette <= 0:
            continue

        # Récupérer les taux
        taux_salarial = coti.get('salarial', 0.0)
        taux_patronal = coti.get('patronal', 0.0)

        # Convertir en float si c'est une string
        if isinstance(taux_salarial, str):
            try:
                taux_salarial = float(taux_salarial)
            except (ValueError, TypeError):
                taux_salarial = 0.0

        if isinstance(taux_patronal, str):
            try:
                taux_patronal = float(taux_patronal)
            except (ValueError, TypeError):
                taux_patronal = 0.0

        # Gestion des taux conditionnels
        if isinstance(taux_patronal, dict):
            if coti_id == 'fnal':
                taux_patronal = taux_patronal.get('taux_moins_50', 0.0) if effectif < 50 else taux_patronal.get('taux_50_et_plus', 0.0)
            elif coti_id == 'CFP':
                taux_patronal = taux_patronal.get('taux_moins_11', 0.0) if effectif < 11 else taux_patronal.get('taux_11_et_plus', 0.0)
            else:
                taux_patronal = 0.0

        # Gestion des taux variables selon le salaire
        if coti_id == 'allocations_familiales':
            taux_patronal = coti.get('patronal_reduit', 0.0) if brut <= 3.5 * smic_mensuel else coti.get('patronal_plein', 0.0)

        if coti_id == 'securite_sociale_maladie':
            taux_patronal = coti.get('patronal_reduit', 0.0) if brut <= 2.5 * smic_mensuel else coti.get('patronal_plein', 0.0)

        if coti_id == 'at_mp':
            taux_patronal = taux_at_mp

        # Exclure CSG et CRDS (gérés séparément)
        if coti_id in ['csg', 'crds']:
            continue

        # Calculer les montants
        if isinstance(taux_salarial, dict):
            # Cas particulier pour les cotisations avec plusieurs composantes
            continue

        montant_salarial = round(assiette * (taux_salarial or 0.0), 2)
        montant_patronal = round(assiette * (taux_patronal or 0.0), 2)

        if montant_salarial == 0 and montant_patronal == 0:
            continue

        # Ajouter à la liste détaillée
        cotisations_detaillees.append({
            "libelle": libelle,
            "base": round(assiette, 2),
            "taux_salarial": taux_salarial if not isinstance(taux_salarial, dict) else None,
            "montant_salarial": montant_salarial,
            "taux_patronal": taux_patronal if not isinstance(taux_patronal, dict) else None,
            "montant_patronal": montant_patronal
        })

        total_salarial += montant_salarial
        total_patronal += montant_patronal

    return cotisations_detaillees, round(total_salarial, 2), round(total_patronal, 2)


def _appliquer_scenario(
    calendrier_base: Dict[str, Any],
    saisies_base: Dict[str, Any],
    scenario_params: Dict[str, Any]
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Applique les paramètres du scénario au calendrier et saisies de base

    Args:
        calendrier_base: Calendrier de base
        saisies_base: Saisies de base
        scenario_params: Paramètres du scénario

    Returns:
        Tuple (calendrier_simule, saisies_simulees)
    """
    calendrier_simule = copy.deepcopy(calendrier_base)
    saisies_simulees = copy.deepcopy(saisies_base)

    # Heures travaillées (override total)
    if "heures_travaillees" in scenario_params:
        heures = scenario_params["heures_travaillees"]
        calendrier_simule["actual_hours"]["heures_reelles"] = heures

    # Heures supplémentaires à 25%
    if "heures_sup_25" in scenario_params and scenario_params["heures_sup_25"] > 0:
        if "actual_hours" not in calendrier_simule:
            calendrier_simule["actual_hours"] = {"evenements": []}
        if "evenements" not in calendrier_simule["actual_hours"]:
            calendrier_simule["actual_hours"]["evenements"] = []

        calendrier_simule["actual_hours"]["evenements"].append({
            "type": "heures_supplementaires",
            "majoration": 25,
            "heures": scenario_params["heures_sup_25"],
            "description": "Heures supplémentaires 25% (simulation)"
        })

    # Heures supplémentaires à 50%
    if "heures_sup_50" in scenario_params and scenario_params["heures_sup_50"] > 0:
        if "actual_hours" not in calendrier_simule:
            calendrier_simule["actual_hours"] = {"evenements": []}
        if "evenements" not in calendrier_simule["actual_hours"]:
            calendrier_simule["actual_hours"]["evenements"] = []

        calendrier_simule["actual_hours"]["evenements"].append({
            "type": "heures_supplementaires",
            "majoration": 50,
            "heures": scenario_params["heures_sup_50"],
            "description": "Heures supplémentaires 50% (simulation)"
        })

    # Primes additionnelles
    if "primes" in scenario_params and isinstance(scenario_params["primes"], list):
        if "primes" not in saisies_simulees:
            saisies_simulees["primes"] = []

        for prime in scenario_params["primes"]:
            saisies_simulees["primes"].append({
                "name": prime.get("name", "Prime simulée"),
                "amount": prime.get("amount", 0.0),
                "is_socially_taxed": prime.get("is_socially_taxed", True),
                "is_taxable": prime.get("is_taxable", True),
                "simulation": True
            })

    # Absences
    if "absences" in scenario_params and isinstance(scenario_params["absences"], list):
        if "absences" not in saisies_simulees:
            saisies_simulees["absences"] = []

        for absence in scenario_params["absences"]:
            saisies_simulees["absences"].append({
                "type": absence.get("type", "absence_non_remuneree"),
                "heures": absence.get("heures", 0.0),
                "jours": absence.get("jours", 0.0),
                "description": absence.get("description", "Absence (simulation)"),
                "simulation": True
            })

    # Congés payés
    if "conges" in scenario_params and isinstance(scenario_params["conges"], list):
        if "conges" not in saisies_simulees:
            saisies_simulees["conges"] = []

        for conge in scenario_params["conges"]:
            saisies_simulees["conges"].append({
                "type": "conges_payes",
                "jours": conge.get("jours", 0.0),
                "date_debut": conge.get("date_debut"),
                "date_fin": conge.get("date_fin"),
                "simulation": True
            })

    return calendrier_simule, saisies_simulees


def comparer_simulation_reel(
    bulletin_simule: Dict[str, Any],
    bulletin_reel: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare un bulletin simulé avec un bulletin réel

    Args:
        bulletin_simule: Bulletin de paie simulé
        bulletin_reel: Bulletin de paie réel

    Returns:
        Dict contenant:
            - differences: Liste des différences par champ
            - summary: Résumé des écarts principaux
            - ecart_total: Écart total sur le net à payer
    """
    logger.info("Comparaison bulletin simulé vs réel")

    differences = []

    # Comparaison du brut
    brut_simule = bulletin_simule.get("salaire_brut", 0.0)
    brut_reel = bulletin_reel.get("salaire_brut", 0.0)
    ecart_brut = brut_simule - brut_reel

    if abs(ecart_brut) > 0.01:
        differences.append({
            "field": "salaire_brut",
            "label": "Salaire brut",
            "simulated_value": brut_simule,
            "real_value": brut_reel,
            "ecart": ecart_brut,
            "ecart_percent": (ecart_brut / brut_reel * 100) if brut_reel > 0 else 0
        })

    # Comparaison des cotisations (total salarial)
    cotis_simule = _calculer_total_cotisations_salariales(bulletin_simule)
    cotis_reel = _calculer_total_cotisations_salariales(bulletin_reel)
    ecart_cotis = cotis_simule - cotis_reel

    if abs(ecart_cotis) > 0.01:
        differences.append({
            "field": "cotisations_salariales",
            "label": "Cotisations salariales",
            "simulated_value": cotis_simule,
            "real_value": cotis_reel,
            "ecart": ecart_cotis,
            "ecart_percent": (ecart_cotis / cotis_reel * 100) if cotis_reel > 0 else 0
        })

    # Comparaison du net à payer
    net_simule = bulletin_simule.get("net_a_payer", 0.0)
    net_reel = bulletin_reel.get("net_a_payer", 0.0)
    ecart_net = net_simule - net_reel

    if abs(ecart_net) > 0.01:
        differences.append({
            "field": "net_a_payer",
            "label": "Net à payer",
            "simulated_value": net_simule,
            "real_value": net_reel,
            "ecart": ecart_net,
            "ecart_percent": (ecart_net / net_reel * 100) if net_reel > 0 else 0
        })

    # Comparaison du net imposable
    net_imp_simule = bulletin_simule.get("synthese_net", {}).get("net_imposable", 0.0)
    net_imp_reel = bulletin_reel.get("synthese_net", {}).get("net_imposable", 0.0)
    ecart_net_imp = net_imp_simule - net_imp_reel

    if abs(ecart_net_imp) > 0.01:
        differences.append({
            "field": "net_imposable",
            "label": "Net imposable",
            "simulated_value": net_imp_simule,
            "real_value": net_imp_reel,
            "ecart": ecart_net_imp,
            "ecart_percent": (ecart_net_imp / net_imp_reel * 100) if net_imp_reel > 0 else 0
        })

    # Comparaison du coût employeur
    cout_simule = bulletin_simule.get("pied_de_page", {}).get("cout_total_employeur", 0.0)
    cout_reel = bulletin_reel.get("pied_de_page", {}).get("cout_total_employeur", 0.0)
    ecart_cout = cout_simule - cout_reel

    if abs(ecart_cout) > 0.01:
        differences.append({
            "field": "cout_total_employeur",
            "label": "Coût total employeur",
            "simulated_value": cout_simule,
            "real_value": cout_reel,
            "ecart": ecart_cout,
            "ecart_percent": (ecart_cout / cout_reel * 100) if cout_reel > 0 else 0
        })

    # Résumé
    summary = {
        "ecart_brut": round(ecart_brut, 2),
        "ecart_cotisations": round(ecart_cotis, 2),
        "ecart_net": round(ecart_net, 2),
        "ecart_net_imposable": round(ecart_net_imp, 2),
        "ecart_cout_employeur": round(ecart_cout, 2),
        "nombre_differences": len(differences)
    }

    return {
        "differences": differences,
        "summary": summary,
        "ecart_total": round(ecart_net, 2)
    }


def _calculer_total_cotisations_salariales(bulletin: Dict[str, Any]) -> float:
    """
    Calcule le total des cotisations salariales d'un bulletin

    Args:
        bulletin: Bulletin de paie

    Returns:
        Total des cotisations salariales
    """
    total = 0.0

    structure = bulletin.get("structure_cotisations", {})

    # Parcourir tous les blocs de cotisations
    for bloc_name in ["bloc_principales", "bloc_allegements", "bloc_autres_contributions", "bloc_csg_non_deductible"]:
        if bloc_name in structure:
            bloc = structure[bloc_name]

            if isinstance(bloc, dict) and "lignes" in bloc:
                lignes = bloc["lignes"]
            elif isinstance(bloc, list):
                lignes = bloc
            else:
                continue

            for ligne in lignes:
                if isinstance(ligne, dict):
                    total += ligne.get("part_salariale", 0.0)

    return total


def generer_scenarios_predefinis(
    employee_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Génère une liste de scénarios de simulation prédéfinis

    Args:
        employee_data: Données employé

    Returns:
        Liste de scénarios prédéfinis
    """
    scenarios = []

    duree_hebdo = employee_data.get("duree_hebdomadaire", 35.0)

    # Scénario 1: Mois complet standard
    scenarios.append({
        "name": "Mois complet standard",
        "description": "Mois travaillé en totalité sans heures sup ni primes",
        "params": {}
    })

    # Scénario 2: Avec heures supplémentaires modérées
    scenarios.append({
        "name": "Heures sup modérées (10h à 25%)",
        "description": "Mois avec 10 heures supplémentaires à 25%",
        "params": {
            "heures_sup_25": 10.0
        }
    })

    # Scénario 3: Avec heures supplémentaires intenses
    scenarios.append({
        "name": "Heures sup intenses (15h à 25% + 5h à 50%)",
        "description": "Mois avec heures supplémentaires importantes",
        "params": {
            "heures_sup_25": 15.0,
            "heures_sup_50": 5.0
        }
    })

    # Scénario 4: Avec prime exceptionnelle
    scenarios.append({
        "name": "Prime exceptionnelle (500€)",
        "description": "Mois avec prime exceptionnelle de 500€",
        "params": {
            "primes": [
                {
                    "name": "Prime exceptionnelle",
                    "amount": 500.0,
                    "is_socially_taxed": True,
                    "is_taxable": True
                }
            ]
        }
    })

    # Scénario 5: Avec absence non rémunérée
    scenarios.append({
        "name": "Absence (3 jours non payés)",
        "description": "Mois avec 3 jours d'absence non rémunérée",
        "params": {
            "absences": [
                {
                    "type": "absence_non_remuneree",
                    "jours": 3.0,
                    "heures": 3.0 * (duree_hebdo / 5),  # 3 jours
                    "description": "Absence non rémunérée"
                }
            ]
        }
    })

    # Scénario 6: Avec congés payés
    scenarios.append({
        "name": "Congés payés (5 jours)",
        "description": "Mois avec 5 jours de congés payés",
        "params": {
            "conges": [
                {
                    "type": "conges_payes",
                    "jours": 5.0,
                    "description": "Congés payés"
                }
            ]
        }
    })

    return scenarios
