# moteur_paie/calcul_brut_forfait.py
"""
Module de calcul du salaire brut pour les employés en forfait jour.

Le forfait jour fonctionne différemment du mode horaire :
- Pas d'heures supplémentaires (forfait annuel)
- Salaire généralement fixe
- Absences déduites en jours, pas en heures
- Pas de calcul de taux horaire
"""

import sys
from .contexte import ContextePaie
from datetime import datetime, date
from typing import Dict, Any, List
from .calcul_conges import calculer_indemnite_conges


def _construire_ligne_avantages_en_nature(contexte: ContextePaie) -> Dict[str, Any] | None:
    """
    Construit la ligne d'avantages en nature (identique au mode horaire).
    """
    total_avantages = 0.0
    regles_aen = contexte.entreprise.get('parametres_paie', {}).get('avantages_en_nature', {})
    situation_salarie_aen = contexte.contrat.get('remuneration', {}).get('avantages_en_nature', {})
    
    situation_repas = situation_salarie_aen.get('repas', {})
    if situation_repas.get('nombre_par_mois', 0) > 0:
        valeur_forfaitaire_repas = regles_aen.get('repas_valeur_forfaitaire', 0.0)
        total_avantages += situation_repas['nombre_par_mois'] * valeur_forfaitaire_repas
    
    situation_logement = situation_salarie_aen.get('logement', {})
    if situation_logement.get('beneficie'):
        bareme_logement = regles_aen.get('logement_bareme_forfaitaire', [])
        salaire_mensuel = contexte.salaire_base_mensuel
        nb_pieces = situation_logement.get('nombre_pieces_principales', 1)
        for tranche in bareme_logement:
            if salaire_mensuel <= tranche.get('remuneration_max', float('inf')):
                valeur = tranche['valeur_1_piece']
                if nb_pieces > 1:
                    valeur += tranche['valeur_par_piece'] * (nb_pieces - 1)
                total_avantages += valeur
                break
    
    if total_avantages > 0:
        return {
            "libelle": "Avantages en nature",
            "quantite": None,
            "taux": None,
            "gain": round(total_avantages, 2),
            "perte": None
        }
    return None


def _calculer_prime_anciennete(contexte: ContextePaie) -> Dict[str, Any] | None:
    """
    Calcule la prime d'ancienneté (identique au mode horaire).
    """
    date_entree_str = contexte.contrat.get('contrat', {}).get('date_entree')
    if not date_entree_str:
        return None
    
    date_entree = datetime.strptime(date_entree_str, "%Y-%m-%d")
    anciennete_annees = (datetime.now() - date_entree).days / 365.25
    idcc = contexte.contrat.get('remuneration', {}).get('convention_collective', {}).get('idcc')
    
    if not idcc:
        return None
    
    regles_cc = contexte.baremes.get('conventions_collectives', {}).get(f"idcc_{idcc}", {})
    regles_prime = regles_cc.get('prime_anciennete', {})
    taux_applicable = 0.0
    
    for palier in regles_prime.get('bareme', []):
        if palier['annees_min'] <= anciennete_annees:
            taux_applicable = palier.get('taux', 0.0)
    
    if taux_applicable == 0.0:
        return None
    
    base_de_calcul = 0.0
    regle_base = regles_prime.get('base_de_calcul', {})
    methode = regle_base.get('methode')
    
    if methode == "salaire_minimum_conventionnel":
        coeff_salarie = contexte.contrat.get('remuneration', {}).get('classification_conventionnelle', {}).get('coefficient')
        for minima in regles_cc.get('salaires_minima', []):
            if minima.get('coefficient') == coeff_salarie:
                base_de_calcul = minima.get('valeur', 0.0)
                break
    elif methode == "pourcentage_salaire_de_base":
        pourcentage = regle_base.get('valeur', 0.0)
        base_de_calcul = contexte.salaire_base_mensuel * pourcentage
    else:
        base_de_calcul = contexte.salaire_base_mensuel
    
    if base_de_calcul == 0.0:
        return None
    
    montant_prime = base_de_calcul * taux_applicable
    return {
        "libelle": f"Prime d'ancienneté ({anciennete_annees:.0f} ans, {taux_applicable * 100:.0f}%)",
        "quantite": base_de_calcul,
        "taux": taux_applicable,
        "gain": round(montant_prime, 2),
        "perte": None
    }


def _calculer_deduction_absence_forfait_jour(
    contexte: ContextePaie,
    nombre_jours_absence: int,
    salaire_journalier: float
) -> Dict[str, Any]:
    """
    Calcule la déduction pour une absence en forfait jour.
    
    Args:
        contexte: Contexte de paie
        nombre_jours_absence: Nombre de jours d'absence
        salaire_journalier: Salaire journalier (salaire mensuel / nombre de jours ouvrés)
    
    Returns:
        Dictionnaire avec les informations de déduction
    """
    montant_deduction = round(nombre_jours_absence * salaire_journalier, 2)
    return {
        "libelle": f"Absence injustifiée ({nombre_jours_absence} jour{'s' if nombre_jours_absence > 1 else ''})",
        "quantite": nombre_jours_absence,
        "taux": round(salaire_journalier, 4),
        "gain": None,
        "perte": montant_deduction
    }


def calculer_salaire_brut_forfait(
    contexte: ContextePaie,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    primes_saisies: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calcule le salaire brut pour un employé en forfait jour.
    
    En forfait jour :
    - Le salaire de base est généralement fixe
    - Pas d'heures supplémentaires
    - Les absences sont déduites en jours
    - Les congés payés sont gérés différemment (maintien de salaire ou 1/10ème)
    
    Args:
        contexte: Contexte de paie
        calendrier_saisie: Liste des événements de paie (jours travaillés/absents)
        date_debut_periode: Date de début de la période de paie
        date_fin_periode: Date de fin de la période de paie
        primes_saisies: Liste des primes exceptionnelles
    
    Returns:
        Dictionnaire avec le salaire brut total et les détails
    """
    lignes_composants_brut = []
    salaire_contractuel = contexte.salaire_base_mensuel
    
    # Calcul du salaire journalier pour les déductions d'absence
    # En forfait jour, on utilise généralement le nombre de jours ouvrés moyens par mois
    # Convention : 21.67 jours ouvrés par mois en moyenne (261 jours / 12 mois)
    jours_ouvres_moyens_mois = 21.67
    salaire_journalier = salaire_contractuel / jours_ouvres_moyens_mois
    
    # 1. Salaire de base (forfait mensuel)
    lignes_composants_brut.append({
        "libelle": "Salaire de base (forfait jour)",
        "quantite": None,
        "taux": None,
        "gain": round(salaire_contractuel, 2),
        "perte": None
    })
    
    # 2. Traitement des événements de la période
    jours_dans_periode = [
        j for j in calendrier_saisie
        if 'date_complete' in j and date_debut_periode <= date.fromisoformat(j['date_complete']) <= date_fin_periode
    ]
    
    jours_conges_dans_periode = []
    nombre_jours_absence_injustifiee = 0
    nombre_jours_travailles = 0
    
    for evenement in jours_dans_periode:
        type_ev = evenement.get('type', '')
        heures = evenement.get('heures', 0.0)
        
        # En forfait jour, heures = 1 signifie "1 jour"
        if type_ev == 'travail_base':
            nombre_jours_travailles += heures
        elif type_ev == 'conges_payes':
            jours_conges_dans_periode.append(evenement)
        elif "absence_injustifiee" in type_ev:
            nombre_jours_absence_injustifiee += heures
            date_absence = date.fromisoformat(evenement['date_complete']).strftime('%d/%m/%y')
            montant_deduction = round(heures * salaire_journalier, 2)
            lignes_composants_brut.append({
                "libelle": f"Absence injustifiée du {date_absence} ({heures:.0f} jour{'s' if heures > 1 else ''})",
                "quantite": heures,
                "taux": round(salaire_journalier, 4),
                "gain": None,
                "perte": montant_deduction
            })
        elif type_ev == 'absence_non_remuneree':
            nombre_jours_absence_injustifiee += heures
            date_absence = date.fromisoformat(evenement['date_complete']).strftime('%d/%m/%y')
            montant_deduction = round(heures * salaire_journalier, 2)
            lignes_composants_brut.append({
                "libelle": f"Absence non rémunérée du {date_absence} ({heures:.0f} jour{'s' if heures > 1 else ''})",
                "quantite": heures,
                "taux": round(salaire_journalier, 4),
                "gain": None,
                "perte": montant_deduction
            })
    
    # 3. Calcul des congés payés
    if jours_conges_dans_periode:
        nombre_jours_conges = len(jours_conges_dans_periode)
        # Pour le forfait jour, on utilise le même calcul que pour les heures
        # mais adapté : on calcule le taux horaire équivalent pour la méthode du maintien
        # En pratique, pour le forfait jour, on utilise souvent la méthode du 1/10ème
        # ou le maintien de salaire
        
        # Calcul d'un taux horaire équivalent pour la compatibilité avec calcul_conges
        # On utilise une base de 7 heures par jour pour le calcul
        heures_equivalentes_conges = nombre_jours_conges * 7.0
        taux_horaire_equivalent = salaire_journalier / 7.0
        
        resultat_conges = calculer_indemnite_conges(
            contexte, nombre_jours_conges, taux_horaire_equivalent
        )
        
        lignes_composants_brut.append({
            "libelle": f"Absence congés payés ({resultat_conges['nombre_jours']} jours)",
            "quantite": round(resultat_conges['total_heures_absence'], 2),
            "taux": None,
            "gain": None,
            "perte": resultat_conges['montant_retenue']
        })
        
        if resultat_conges["methode_retenue"] == "Maintien":
            lignes_composants_brut.append({
                "libelle": "Indemnité de congés payés (maintien de salaire)",
                "quantite": round(resultat_conges['heures_base'], 2),
                "taux": round(taux_horaire_equivalent, 4),
                "gain": resultat_conges['indemnite_maintien_base'],
                "perte": None
            })
            if resultat_conges['indemnite_maintien_hs'] > 0:
                lignes_composants_brut.append({
                    "libelle": "Indemnité de congés payés (partie HS)",
                    "quantite": round(resultat_conges['heures_hs'], 2),
                    "taux": round(taux_horaire_equivalent * 1.25, 4),
                    "gain": resultat_conges['indemnite_maintien_hs'],
                    "perte": None
                })
        else:
            lignes_composants_brut.append({
                "libelle": "Indemnité de congés payés (règle du 1/10ème)",
                "quantite": None,
                "taux": None,
                "gain": resultat_conges['montant_indemnite'],
                "perte": None
            })
    
    # 4. Ajout des primes, avantages et calcul des totaux
    ligne_prime_anciennete = _calculer_prime_anciennete(contexte)
    if ligne_prime_anciennete:
        lignes_composants_brut.append(ligne_prime_anciennete)
    
    if primes_saisies:
        for prime in primes_saisies:
            lignes_composants_brut.append({
                "libelle": prime.get('libelle', 'Prime'),
                "quantite": None,
                "taux": None,
                "gain": prime.get('montant', 0.0),
                "perte": None
            })
    
    ligne_aen = _construire_ligne_avantages_en_nature(contexte)
    if ligne_aen:
        lignes_composants_brut.append(ligne_aen)
    
    # Calcul du brut total
    total_gains = sum(
        l.get('gain', 0.0) or 0.0 
        for l in lignes_composants_brut 
        if not l.get('is_sous_total')
    )
    total_pertes = sum(l.get('perte', 0.0) or 0.0 for l in lignes_composants_brut)
    
    # Protection : Les déductions d'absence ne peuvent pas dépasser le salaire de base
    # (sauf si des primes/avantages sont ajoutés)
    salaire_base_seul = salaire_contractuel
    if total_pertes > salaire_base_seul:
        print(
            f"AVERTISSEMENT: Les déductions d'absence ({total_pertes:.2f} €) "
            f"dépassent le salaire de base ({salaire_base_seul:.2f} €). "
            f"Les déductions sont limitées au salaire de base.",
            file=sys.stderr
        )
        # Limiter les déductions au salaire de base uniquement
        # (les primes et avantages peuvent compenser)
        total_pertes = min(total_pertes, salaire_base_seul)
    
    total_brut = total_gains - total_pertes
    
    # Protection finale : Le brut ne peut pas être négatif
    if total_brut < 0:
        print(
            f"AVERTISSEMENT: Le salaire brut calculé est négatif ({total_brut:.2f} €). "
            f"Il est ramené à 0 €.",
            file=sys.stderr
        )
        total_brut = 0.0
    
    # En forfait jour, pas d'heures supplémentaires
    remuneration_hs_totale = 0.0
    total_heures_supp = 0.0
    
    return {
        "salaire_brut_total": round(total_brut, 2),
        "lignes_composants_brut": lignes_composants_brut,
        "remuneration_brute_heures_supp": round(remuneration_hs_totale, 2),
        "total_heures_supp": round(total_heures_supp, 2),
        "nombre_jours_travailles": round(nombre_jours_travailles, 2),
        "nombre_jours_absence": round(nombre_jours_absence_injustifiee, 2)
    }
