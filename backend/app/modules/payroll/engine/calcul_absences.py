import sys
from datetime import date, timedelta
from typing import Dict, Any
from .contexte import ContextePaie

def _compter_heures_absence(
    contexte: ContextePaie, 
    date_debut: date, 
    date_fin: date
) -> float:
    """Compte le nombre d'heures de travail contractuelles durant une période d'absence."""
    heures_absence = 0.0
    heures_par_jour = contexte.duree_hebdo_contrat / 5  # Suppose une semaine de 5 jours ouvrés

    current_date = date_debut
    while current_date <= date_fin:
        # On ne décompte que les jours de semaine (lundi=0, dimanche=6)
        if current_date.weekday() < 5:
            heures_absence += heures_par_jour
        current_date += timedelta(days=1)
        
    return heures_absence

def calculer_deduction_absence(
    contexte: ContextePaie, 
    absence: Dict[str, Any],
    taux_horaire: float
) -> Dict[str, Any]:
    """
    Calcule la déduction sur salaire pour une absence non rémunérée.
    La méthode est celle du taux horaire réel.
    """
    print(f"INFO: Calcul de la déduction pour l'absence '{absence.get('libelle')}'...", file=sys.stderr)
    
    date_debut = date.fromisoformat(absence['date_debut'])
    date_fin = date.fromisoformat(absence['date_fin'])
    
    nombre_heures_absence = _compter_heures_absence(contexte, date_debut, date_fin)
    
    if nombre_heures_absence == 0:
        return None
        
    montant_deduction = round(nombre_heures_absence * taux_horaire, 2)
    
    libelle_final = f"{absence.get('libelle', 'Absence')} du {date_debut.strftime('%d/%m')} au {date_fin.strftime('%d/%m')}"
    
    return {
        "libelle": libelle_final,
        "quantite": nombre_heures_absence,
        "taux": round(taux_horaire, 4),
        "gain": None,
        "perte": montant_deduction
    }