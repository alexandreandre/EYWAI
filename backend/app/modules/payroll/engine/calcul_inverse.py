"""
Module de calcul inverse : détermination du brut nécessaire pour un net cible
Utilise une recherche dichotomique pour converger vers le brut exact.

Chaque essai est un bulletin du moteur complet, celui du bulletin d'essai
(`run_simulation_bulletin_pipeline`) : période choisie à l'écran, barèmes
chargés (refusés s'ils sont d'une année passée : la simulation n'affiche pas d'alerte),
contribution CPF des seuls CDD, réduction générale (rejeu G.9, 11/10/2026).
"""

import copy
from datetime import datetime
from typing import Dict, Any, Optional, Literal, Tuple
from zoneinfo import ZoneInfo
import logging

from app.modules.payroll.engine.baremes_loader import refuser_baremes_d_une_annee_passee

logger = logging.getLogger(__name__)

#: Le contrat retenu quand ni l'écran ni la fiche n'en donnent : l'écran du
#: calcul inverse ne demande pas le type de contrat, et la réponse le dit.
TYPE_CONTRAT_PAR_DEFAUT = "CDI"


def _periode(month: Optional[int], year: Optional[int]) -> Tuple[int, int]:
    """La période demandée ; à défaut, le mois en cours (heure de Paris)."""
    maintenant = datetime.now(ZoneInfo("Europe/Paris"))
    return int(month or maintenant.month), int(year or maintenant.year)


class CalculInverseError(Exception):
    """Exception levée en cas d'erreur dans le calcul inverse"""

    pass


class NonConvergenceError(CalculInverseError):
    """Exception levée quand l'algorithme ne converge pas"""

    pass


def estimer_coefficient_net_brut(statut: str, taux_pas: float = 0.0) -> float:
    """
    Estime le coefficient de conversion net/brut selon le statut

    Args:
        statut: "Cadre" ou "Non-cadre"
        taux_pas: Taux de prélèvement à la source (0-100)

    Returns:
        Coefficient multiplicateur (ex: 1.28 pour non-cadre)
    """
    # Coefficients de base (cotisations salariales moyennes)
    coefficients_base = {
        "Cadre": 1.30,  # ~23% de cotisations salariales
        "Non-cadre": 1.28,  # ~22% de cotisations salariales
    }

    coefficient = coefficients_base.get(statut, 1.28)

    # Ajustement selon le taux PAS
    if taux_pas > 0:
        # Plus le taux PAS est élevé, plus le coefficient augmente
        ajustement_pas = (taux_pas / 100) * 0.15
        coefficient += ajustement_pas

    return coefficient


def calculer_brut_depuis_net(
    net_cible: float,
    type_net: Literal["net_a_payer", "net_imposable"],
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
    calendrier: Dict[str, Any],
    saisies: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    tolerance: float = 1.0,
    max_iterations: int = 25,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calcule le brut nécessaire pour obtenir un net cible via recherche dichotomique

    Args:
        net_cible: Montant net souhaité
        type_net: "net_a_payer" ou "net_imposable"
        employee_data: Données employé (contrat, statut, etc.)
        company_data: Données entreprise
        baremes: Barèmes de cotisations
        calendrier: Calendrier de travail (heures planifiées/réelles)
        saisies: Saisies mensuelles (primes, absences, etc.)
        options: Options supplémentaires pour la simulation
        tolerance: Tolérance d'écart acceptable (en euros)
        max_iterations: Nombre maximum d'itérations
        month, year: Période du calcul (celle de l'écran) ; à défaut, le mois en cours

    Returns:
        Dict contenant:
            - brut_calcule: Salaire brut trouvé
            - net_obtenu: Net réellement obtenu
            - ecart: Différence net_obtenu - net_cible
            - iterations: Nombre d'itérations effectuées
            - bulletin_complet: Bulletin de paie complet
            - cout_employeur: Coût total employeur
            - convergence: True si convergence atteinte
            - month, year: Période du calcul
            - type_contrat: Contrat retenu ; type_contrat_par_defaut: True s'il
              n'était pas donné (un CDI)

    Raises:
        CalculInverseError: Si les paramètres sont invalides
        NonConvergenceError: Si l'algorithme ne converge pas
        BaremesDUneAnneePassee: Si les barèmes chargés sont d'une année
            antérieure à la période (le bulletin, lui, se calcule avec une alerte)
    """
    # Validation des entrées
    if net_cible <= 0:
        raise CalculInverseError("Le net cible doit être strictement positif")

    if type_net not in ["net_a_payer", "net_imposable"]:
        raise CalculInverseError(f"Type de net invalide: {type_net}")

    month, year = _periode(month, year)
    # Barèmes d'une année passée : refus (le bulletin, lui, se calcule avec une
    # alerte ; la simulation n'en affiche pas, son chiffre serait faux en silence).
    refuser_baremes_d_une_annee_passee(baremes or {}, year)

    type_contrat = str(
        employee_data.get("type_contrat") or employee_data.get("contract_type") or ""
    ).strip()
    type_contrat_par_defaut = not type_contrat
    employee_data = {
        **employee_data,
        "type_contrat": type_contrat or TYPE_CONTRAT_PAR_DEFAUT,
    }

    # Récupération du statut et du taux PAS
    statut = employee_data.get("statut", "Non-cadre")
    taux_pas = employee_data.get("taux_prelevement_source", 0.0)

    # Estimation initiale des bornes
    coefficient = estimer_coefficient_net_brut(statut, taux_pas)

    logger.info(
        f"Calcul inverse: net_cible={net_cible}€, type={type_net}, statut={statut}"
    )
    logger.info(f"Coefficient estimé: {coefficient}")

    # Bornes initiales (large pour garantir l'encadrement)
    borne_min = net_cible * coefficient * 0.95
    borne_max = net_cible * coefficient * 1.20

    meilleur_resultat = None
    meilleur_ecart = float("inf")
    # Un seul contexte construit, copié à chaque essai (barèmes partagés).
    contexte_de_base = _contexte_de_base(employee_data, company_data, baremes)

    for iteration in range(1, max_iterations + 1):
        # Estimation du brut (milieu de l'intervalle)
        brut_estime = (borne_min + borne_max) / 2

        logger.debug(
            f"Itération {iteration}: brut_estime={brut_estime:.2f}€ (bornes: {borne_min:.2f} - {borne_max:.2f})"
        )

        try:
            # Calcul du bulletin complet avec ce brut
            bulletin = _calculer_bulletin_avec_brut_override(
                brut_estime,
                employee_data,
                company_data,
                baremes,
                calendrier,
                saisies,
                options,
                month=month,
                year=year,
                contexte_de_base=contexte_de_base,
            )

            # Extraction du net selon le type demandé
            net_obtenu = _extraire_net_du_bulletin(bulletin, type_net)

            # Calcul de l'écart
            ecart = net_obtenu - net_cible
            ecart_abs = abs(ecart)

            logger.debug(f"  → net_obtenu={net_obtenu:.2f}€, écart={ecart:.2f}€")

            # Sauvegarde du meilleur résultat
            if ecart_abs < meilleur_ecart:
                meilleur_ecart = ecart_abs
                meilleur_resultat = {
                    # Le brut du bulletin : le salaire de base cherché, plus ce
                    # que le moteur y ajoute (heures supplémentaires d'un
                    # horaire au-delà de 35 h).
                    "brut_calcule": float(bulletin.get("salaire_brut") or brut_estime),
                    "net_obtenu": net_obtenu,
                    "ecart": ecart,
                    "iterations": iteration,
                    "bulletin_complet": bulletin,
                    "cout_employeur": _calculer_cout_employeur(bulletin),
                    "convergence": ecart_abs < tolerance,
                    "month": month,
                    "year": year,
                    "type_contrat": employee_data["type_contrat"],
                    "type_contrat_par_defaut": type_contrat_par_defaut,
                }

            # Vérification de la convergence
            if ecart_abs < tolerance:
                logger.info(
                    f"Convergence atteinte en {iteration} itérations (écart: {ecart:.2f}€)"
                )
                return meilleur_resultat

            # Ajustement des bornes
            if ecart > 0:
                # On a trop de net, il faut diminuer le brut
                borne_max = brut_estime
            else:
                # Pas assez de net, il faut augmenter le brut
                borne_min = brut_estime

            # Vérification de l'intervalle minimal
            if (borne_max - borne_min) < 0.01:
                logger.warning(f"Intervalle trop petit après {iteration} itérations")
                break

        except Exception as e:
            logger.error(f"Erreur lors de l'itération {iteration}: {str(e)}")
            # Continuer avec l'itération suivante
            continue

    # Si on arrive ici, on n'a pas convergé dans le nombre d'itérations
    if meilleur_resultat is not None:
        logger.warning(
            f"Non-convergence: meilleur écart={meilleur_ecart:.2f}€ après {max_iterations} itérations"
        )
        return meilleur_resultat
    else:
        raise NonConvergenceError(
            f"Impossible de converger après {max_iterations} itérations. "
            f"Vérifiez les données d'entrée."
        )


def _contexte_de_base(
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
) -> Any:
    """Le contexte du moteur pour ce salarié, construit une fois (comme celui
    du bulletin d'essai)."""
    from .contexte import ChargerContexte

    return ChargerContexte(employee_data, company_data, baremes)


def _calculer_bulletin_avec_brut_override(
    brut_force: float,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
    calendrier: Dict[str, Any],
    saisies: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    *,
    month: int,
    year: int,
    contexte_de_base: Any = None,
) -> Dict[str, Any]:
    """
    Calcule un bulletin complet pour un salaire de base donné, avec le moteur
    du bulletin d'essai : cotisations selon le contrat (la contribution CPF
    des seuls CDD), réduction générale, période et barèmes de l'année.

    Args:
        brut_force: Salaire de base essayé
        employee_data: Données employé (type de contrat déjà résolu)
        company_data: Données entreprise
        baremes: Barèmes chargés depuis la base de données
        calendrier: Non utilisé (mois complet travaillé, comme le bulletin d'essai)
        saisies: Non utilisé
        options: Options supplémentaires
        month, year: Période du bulletin
        contexte_de_base: Contexte déjà construit pour ce salarié, copié ici

    Returns:
        Bulletin de paie du moteur
    """
    from .simulation_pipeline import run_simulation_bulletin_pipeline

    if contexte_de_base is None:
        contexte_de_base = _contexte_de_base(employee_data, company_data, baremes)
    # Chaque essai part d'une copie neuve (le moteur pose des alertes et des
    # détails sur le contexte) ; les barèmes, lus seulement, sont partagés.
    contexte = copy.deepcopy(
        contexte_de_base, {id(contexte_de_base.baremes): contexte_de_base.baremes}
    )
    contexte.contrat.setdefault("remuneration", {})["salaire_de_base"] = {
        "valeur": float(brut_force)
    }
    return run_simulation_bulletin_pipeline(contexte, month=month, year=year)


def _extraire_net_du_bulletin(bulletin: Dict[str, Any], type_net: str) -> float:
    """
    Extrait le montant net du bulletin selon le type demandé

    Args:
        bulletin: Bulletin de paie complet
        type_net: "net_a_payer" ou "net_imposable"

    Returns:
        Montant net
    """
    if type_net == "net_a_payer":
        return bulletin.get("net_a_payer", 0.0)
    elif type_net == "net_imposable":
        synthese = bulletin.get("synthese_net", {})
        return synthese.get("net_imposable", 0.0)
    else:
        raise ValueError(f"Type de net invalide: {type_net}")


def _calculer_cout_employeur(bulletin: Dict[str, Any]) -> float:
    """
    Calcule le coût total employeur à partir du bulletin

    Args:
        bulletin: Bulletin de paie complet

    Returns:
        Coût total employeur
    """
    pied_de_page = bulletin.get("pied_de_page", {})
    return pied_de_page.get("cout_total_employeur", 0.0)


def simuler_avec_net_cible(
    employee_id: str,
    net_cible: float,
    type_net: str,
    month: int,
    year: int,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fonction de haut niveau pour simuler un bulletin à partir d'un net cible

    Cette fonction charge automatiquement les données nécessaires et lance
    le calcul inverse.

    Args:
        employee_id: ID de l'employé
        net_cible: Net souhaité
        type_net: "net_a_payer" ou "net_imposable"
        month: Mois (1-12)
        year: Année
        options: Options de simulation

    Returns:
        Résultat du calcul inverse

    Note:
        Cette fonction nécessite l'accès à la base de données Supabase
        pour charger les données employé/entreprise/barèmes
    """
    # TODO: Implémenter le chargement depuis Supabase
    # Pour l'instant, cette fonction est un placeholder
    raise NotImplementedError(
        "Cette fonction nécessite l'intégration avec Supabase. "
        "Utilisez calculer_brut_depuis_net() avec les données chargées manuellement."
    )


# Fonction de commodité pour tests
def calculer_brut_simple(
    net_cible: float, statut: str = "Non-cadre", taux_pas: float = 0.0
) -> Dict[str, Any]:
    """
    Calcul simplifié du brut (estimation rapide sans calcul complet)

    Args:
        net_cible: Net souhaité
        statut: "Cadre" ou "Non-cadre"
        taux_pas: Taux PAS (0-100)

    Returns:
        Dict avec brut_estime et coefficient
    """
    coefficient = estimer_coefficient_net_brut(statut, taux_pas)
    brut_estime = net_cible * coefficient

    return {
        "brut_estime": round(brut_estime, 2),
        "coefficient": coefficient,
        "net_cible": net_cible,
        "statut": statut,
        "taux_pas": taux_pas,
        "precision": "estimation_rapide",
    }
