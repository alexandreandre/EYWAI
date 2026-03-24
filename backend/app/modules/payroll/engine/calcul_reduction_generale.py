# moteur_paie/calcul_reduction_generale.py

import sys
from typing import Dict, Any, List

# Note: Ce module suppose l'existence d'un objet "contexte" qui contient
# les informations de l'employé, de l'entreprise et les barèmes/taux.

def _calculer_parametre_T(contexte: 'ContextePaie') -> float:
    """
    Calcule dynamiquement le paramètre T en additionnant les taux de cotisations
    patronales concernées par la réduction générale.
    
    Cette méthode est plus robuste qu'un T hardcodé car elle s'adapte
    aux changements de législation si le fichier cotisations.json est à jour.
    """
    taux_a_sommer = {}
    cotisations_data = contexte.baremes.get('cotisations', {}).get('cotisations', [])
    
    # On convertit la liste en dictionnaire pour un accès facile par ID
    catalogue_cotisations = {c['id']: c for c in cotisations_data}

    # 1. Taux fixes
    taux_a_sommer['maladie'] = catalogue_cotisations.get('securite_sociale_maladie', {}).get('patronal_reduit', 0.0)
    taux_a_sommer['allocations_familiales'] = catalogue_cotisations.get('allocations_familiales', {}).get('patronal_reduit', 0.0)
    taux_a_sommer['vieillesse_plaf'] = catalogue_cotisations.get('retraite_secu_plafond', {}).get('patronal', 0.0)
    taux_a_sommer['vieillesse_deplaf'] = catalogue_cotisations.get('retraite_secu_deplafond', {}).get('patronal', 0.0)
    taux_a_sommer['csa'] = catalogue_cotisations.get('csa', {}).get('patronal', 0.0)
    taux_a_sommer['chomage'] = catalogue_cotisations.get('assurance_chomage', {}).get('patronal', 0.0)
    
    # 2. Taux de retraite complémentaire (T1 uniquement)
    taux_a_sommer['retraite_comp_t1'] = catalogue_cotisations.get('retraite_comp_t1', {}).get('patronal', 0.0)
    taux_a_sommer['ceg_t1'] = catalogue_cotisations.get('ceg_t1', {}).get('patronal', 0.0)
    
    # 3. Taux variables selon l'entreprise
    effectif = contexte.entreprise.get('effectif', 0)
    fnal_taux = catalogue_cotisations.get('fnal', {}).get('patronal', {})
    if effectif >= 50:
        taux_a_sommer['fnal'] = fnal_taux.get('taux_50_et_plus', 0.0)
    else:
        taux_a_sommer['fnal'] = fnal_taux.get('taux_moins_50', 0.0)

    # 4. Taux AT/MP (spécifique à l'entreprise/employé)
    # Il est essentiel que ce taux soit correctement renseigné.
    taux_at_mp = contexte.entreprise.get('parametres_paie', {}).get('taux_at_mp', 0.0)
    if not taux_at_mp:
        print("AVERTISSEMENT: Le taux AT/MP n'est pas défini. La réduction générale sera sous-évaluée.", file=sys.stderr)
    taux_a_sommer['at_mp'] = taux_at_mp

    parametre_T = sum(taux_a_sommer.values())
    
    # Le T est plafonné à une valeur maximale (en 2025, 0.3333 pour un taux AT/MP de 1.50%).
    # On peut ajouter un plafond de sécurité si nécessaire, mais le calcul dynamique est la norme.
    
    print(f"DEBUG [Réduction]: Calcul du paramètre T = {parametre_T:.6f}", file=sys.stderr)
    return parametre_T

# Dans moteur_paie/calcul_reduction_generale.py

def _calculer_smic_de_reference_cumule(contexte: 'ContextePaie', heures_remunerees_cumulees: float) -> float:
    """
    Calcule le SMIC de référence CUMULÉ depuis le début de l'année en utilisant la structure
    telle que chargée par la classe ContextePaie.
    """
    # --- CORRECTION DÉFINITIVE ---
    # Chemin d'accès direct : baremes -> 'smic' -> 'cas_general'
    smic_horaire = contexte.baremes.get('smic', {}).get('cas_general', 0.0)
    
    if not smic_horaire:
        raise ValueError("SMIC horaire (cas_general) non trouvé dans les barèmes.")
        
    smic_reference_cumule = smic_horaire * heures_remunerees_cumulees
    
    print(f"DEBUG [Réduction]: SMIC de référence cumulé = {smic_reference_cumule:.2f} € (pour {heures_remunerees_cumulees:.2f}h)", file=sys.stderr)
    
    return smic_reference_cumule

def calculer_reduction_generale(
    contexte: 'ContextePaie',
    salaire_brut_mois: float,
    heures_remunerees_mois: float,
) -> dict[str, any] | None:
    """
    Calcule le montant de la Réduction Générale avec régularisation progressive.
    C'est la méthode officielle et obligatoire.

    Args:
        contexte: L'objet contexte contenant toutes les données nécessaires.
        salaire_brut_mois: Le salaire brut du mois en cours.
        heures_remunerees_mois: Le total des heures du mois qui entrent dans le
                               calcul du SMIC de référence (travail, HS, CP, etc.).
    """
    print("INFO: Démarrage du calcul de la Réduction Générale (méthode de régularisation progressive)...", file=sys.stderr)

    # --- ÉTAPE 1 : Récupérer les données cumulées du mois précédent ---
    # Gérer le cas où contexte.cumuls est None ou n'existe pas
    if contexte.cumuls is None:
        contexte.cumuls = {}
    cumuls_precedents = contexte.cumuls.get('cumuls', {}) if isinstance(contexte.cumuls, dict) else {}
    brut_cumule_annee_N_1 = cumuls_precedents.get('brut_total', 0.0)
    heures_cumulees_annee_N_1 = cumuls_precedents.get('heures_remunerees', 0.0)
    reduction_deja_appliquee_N_1 = abs(cumuls_precedents.get('reduction_generale_patronale', 0.0))

    # --- ÉTAPE 2 : Calculer les nouveaux cumuls pour le mois en cours ---
    brut_total_cumule = brut_cumule_annee_N_1 + salaire_brut_mois
    heures_total_cumulees = heures_cumulees_annee_N_1 + heures_remunerees_mois

    # --- ÉTAPE 3 : Calculer les paramètres de la formule sur les cumuls ---
    parametre_T = _calculer_parametre_T(contexte)
    smic_reference_total_cumule = _calculer_smic_de_reference_cumule(contexte, heures_total_cumulees)
    
    # --- ÉTAPE 4 : Appliquer la formule de la réduction générale sur les cumuls ---
    seuil_eligibilite_cumule = 1.6 * smic_reference_total_cumule
    
    if brut_total_cumule >= seuil_eligibilite_cumule:
        print(f"INFO: Brut cumulé ({brut_total_cumule:.2f} €) >= 1.6 * SMIC cumulé ({seuil_eligibilite_cumule:.2f} €). La réduction totale est de 0.", file=sys.stderr)
        # S'il y a eu une réduction les mois précédents, il faut la "rembourser".
        montant_reduction_mois = -reduction_deja_appliquee_N_1
        coefficient_C = 0.0
        reduction_totale_due = 0.0  # LIGNE CORRIGÉE : Initialise la variable dans ce cas
    
    else:
        # Formule : C = (T / 0,6) × ([1,6 × SMIC cumulé / Rémunération brute cumulée] - 1)
        if brut_total_cumule == 0:
            return None # Division par zéro, pas de salaire, pas de réduction.
            
        coefficient_C = (parametre_T / 0.6) * ( (seuil_eligibilite_cumule / brut_total_cumule) - 1 )
        coefficient_C = min(max(0, coefficient_C), parametre_T) # Le coefficient est borné entre 0 et T

        reduction_totale_due = brut_total_cumule * coefficient_C
        
        # --- ÉTAPE 5 : Calculer la réduction du mois par différence ---
        montant_reduction_mois = reduction_totale_due - reduction_deja_appliquee_N_1
    
    montant_final = -round(montant_reduction_mois, 2)

    print(f"DEBUG [Réduction]: Coeff C cumulé = {coefficient_C:.6f} | Réduction totale due = {reduction_totale_due:.2f} €", file=sys.stderr)
    print(f"DEBUG [Réduction]: Déjà appliqué = {reduction_deja_appliquee_N_1:.2f} € | Montant du mois = {montant_final} €", file=sys.stderr)

    return {
        "libelle": "Réduction générale de cotisations patronales",
        "base": salaire_brut_mois,
        "taux_salarial": None,
        "montant_salarial": 0.0,
        "taux_patronal": round(coefficient_C, 6) if coefficient_C > 0 else None,
        "montant_patronal": montant_final,
        # Info supplémentaire pour la mise à jour des cumuls
        "valeur_cumulative_a_enregistrer": round(reduction_totale_due, 2)
    }