"""
Module de calcul inverse : détermination du brut nécessaire pour un net cible
Utilise une recherche dichotomique pour converger vers le brut exact
"""

from typing import Dict, Any, Optional, Literal
import logging

logger = logging.getLogger(__name__)


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

    Returns:
        Dict contenant:
            - brut_calcule: Salaire brut trouvé
            - net_obtenu: Net réellement obtenu
            - ecart: Différence net_obtenu - net_cible
            - iterations: Nombre d'itérations effectuées
            - bulletin_complet: Bulletin de paie complet
            - cout_employeur: Coût total employeur
            - convergence: True si convergence atteinte

    Raises:
        CalculInverseError: Si les paramètres sont invalides
        NonConvergenceError: Si l'algorithme ne converge pas
    """
    # Validation des entrées
    if net_cible <= 0:
        raise CalculInverseError("Le net cible doit être strictement positif")

    if type_net not in ["net_a_payer", "net_imposable"]:
        raise CalculInverseError(f"Type de net invalide: {type_net}")

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
                    "brut_calcule": brut_estime,
                    "net_obtenu": net_obtenu,
                    "ecart": ecart,
                    "iterations": iteration,
                    "bulletin_complet": bulletin,
                    "cout_employeur": _calculer_cout_employeur(bulletin),
                    "convergence": ecart_abs < tolerance,
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


def _calculer_bulletin_avec_brut_override(
    brut_force: float,
    employee_data: Dict[str, Any],
    company_data: Dict[str, Any],
    baremes: Dict[str, Any],
    calendrier: Dict[str, Any],
    saisies: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calcule un bulletin complet en forçant un brut spécifique

    Utilise la fonction de simulation avec les taux réels de la base de données.

    Args:
        brut_force: Brut à atteindre
        employee_data: Données employé
        company_data: Données entreprise
        baremes: Barèmes chargés depuis la base de données
        calendrier: Calendrier (non utilisé dans cette version simplifiée)
        saisies: Saisies (non utilisé dans cette version simplifiée)
        options: Options supplémentaires

    Returns:
        Bulletin de paie avec taux réels
    """
    options = options or {}

    # Importer la fonction de calcul détaillé depuis simulation
    from .simulation import _creer_bulletin_simplifie

    # Préparer les paramètres du scénario avec le brut forcé
    scenario_params = {"salaire_base_override": brut_force}

    # Appeler la fonction qui utilise les taux réels
    bulletin = _creer_bulletin_simplifie(
        employee_data,
        company_data,
        scenario_params,
        month=1,  # Non utilisé pour le calcul inverse, mais requis
        year=2025,  # Non utilisé pour le calcul inverse, mais requis
        baremes=baremes,
    )

    return bulletin


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
