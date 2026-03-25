# moteur_paie/calcul_net.py
import sys
import os
from .contexte import ContextePaie
from typing import Dict, Any, List
from supabase import create_client, Client

def _get_safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)

# Dans le fichier moteur_paie/calcul_net.py

# Dans le fichier moteur_paie/calcul_net.py

def _calculer_net_imposable(
    contexte: ContextePaie, 
    salaire_brut: float, 
    total_cotisations_salariales: float, 
    lignes_cotisations: List[Dict[str, Any]],
    remuneration_heures_supp: float, # <-- NOUVEAU: On passe le montant des HS
    primes_soumises_impot: List[Dict[str, Any]] = None # <-- NOUVEAU: Primes soumises à l'impôt (ex: PPV si effectif >= 50)
) -> float:
    if primes_soumises_impot is None:
        primes_soumises_impot = []

    montant_csg_non_deductible = 0.0
    for ligne in lignes_cotisations:
        libelle = ligne.get('libelle', '').lower()
        if "csg/crds" in libelle and "non déductible" in libelle:
            montant_csg_non_deductible += _get_safe_float(ligne.get('montant_salarial'))
    
    mutuelle_spec = contexte.contrat.get('specificites_paie', {}).get('mutuelle', {})
    part_patronale_mutuelle = 0.0
    if mutuelle_spec.get('adhesion'):
        # Nouveau format : charger depuis company_mutuelle_types si mutuelle_type_ids présent
        mutuelle_type_ids = mutuelle_spec.get('mutuelle_type_ids', [])
        if mutuelle_type_ids:
            # Charger les formules depuis la base de données
            try:
                supabase_url = os.environ.get("SUPABASE_URL")
                supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
                if supabase_url and supabase_key:
                    supabase_client: Client = create_client(supabase_url, supabase_key)
                    mutuelles_response = supabase_client.table('company_mutuelle_types') \
                        .select("*") \
                        .in_('id', mutuelle_type_ids) \
                        .eq('is_active', True) \
                        .execute()
                    
                    if mutuelles_response.data:
                        for mutuelle in mutuelles_response.data:
                            # On ajoute la part patronale seulement si soumise à CSG
                            if mutuelle.get('part_patronale_soumise_a_csg', True):
                                part_patronale_mutuelle += _get_safe_float(mutuelle.get('montant_patronal'))
                else:
                    print("WARN: Variables Supabase non configurées, impossible de charger les mutuelles depuis la BDD", file=sys.stderr)
            except Exception as e:
                print(f"ERREUR: Impossible de charger les mutuelles depuis la BDD: {e}", file=sys.stderr)
                # Fallback sur l'ancien format si erreur
        
        # Ancien format : lignes_specifiques (rétrocompatibilité)
        for ligne in mutuelle_spec.get('lignes_specifiques', []):
            # On ajoute la part patronale seulement si la ligne est marquée comme soumise à CSG
            if ligne.get('part_patronale_soumise_a_csg', True):
                part_patronale_mutuelle += _get_safe_float(ligne.get('montant_patronal'))
    
    salaire_brut_safe = _get_safe_float(salaire_brut)
    total_cotisations_safe = _get_safe_float(total_cotisations_salariales)
    
    # --- Formule standard du net imposable "brut" ---
    net_imposable_avant_defiscalisation = (salaire_brut_safe - total_cotisations_safe) + montant_csg_non_deductible + part_patronale_mutuelle
    
    # --- NOUVEAU : Application de la défiscalisation des HS ---
    # On soustrait le montant brut des HS (en s'assurant de ne pas dépasser le plafond annuel un jour)
    # Pour l'instant, on applique la défiscalisation sur tout le montant.
    net_imposable_apres_hs = net_imposable_avant_defiscalisation - remuneration_heures_supp
    
    # --- NOUVEAU : Ajout des primes soumises à l'impôt (ex: PPV si effectif >= 50) ---
    montant_primes_soumises_impot = 0.0
    for prime in primes_soumises_impot:
        montant_prime = _get_safe_float(prime.get('montant'))
        montant_primes_soumises_impot += montant_prime
    
    net_imposable_final = net_imposable_apres_hs + montant_primes_soumises_impot

    # Le bloc de debug détaillé
    print("\n--- Calcul du Net Imposable ---", file=sys.stderr)
    print(f"\t  Net Social (Net à payer av. impôt) : {salaire_brut_safe - total_cotisations_safe:10.2f} €", file=sys.stderr)
    print(f"\t+ CSG/CRDS non déductible          : {montant_csg_non_deductible:10.2f} €", file=sys.stderr)
    print(f"\t+ Part Patronale Mutuelle          : {part_patronale_mutuelle:10.2f} €", file=sys.stderr)
    print("\t--------------------------------------------", file=sys.stderr)
    print(f"\t= Imposable avant défiscalisation  : {net_imposable_avant_defiscalisation:10.2f} €", file=sys.stderr)
    print(f"\t- Exonération Heures Supp.         : {remuneration_heures_supp:10.2f} €", file=sys.stderr)
    if montant_primes_soumises_impot > 0:
        print(f"\t+ Primes soumises à l'impôt        : {montant_primes_soumises_impot:10.2f} €", file=sys.stderr)
    print("\t--------------------------------------------", file=sys.stderr)
    print(f"\t= NET IMPOSABLE                    : {round(net_imposable_final, 2):10.2f} €", file=sys.stderr)
    print("---------------------------------\n", file=sys.stderr)
    
    return round(net_imposable_final, 2)

def _calculer_prelevement_a_la_source(contexte: ContextePaie, net_imposable: float ) -> float:
    taux_pas = _get_safe_float(contexte.contrat.get('specificites_paie', {}).get('prelevement_a_la_source', {}).get('taux'))
    montant_pas = _get_safe_float(net_imposable) * (taux_pas / 100.0)
    return round(montant_pas, 2)



def _calculer_net_a_payer(net_social: float, montant_pas: float, contexte: ContextePaie, primes_non_soumises: List[Dict[str, Any]], montant_acompte: float = 0.0, primes_soumises_impot: List[Dict[str, Any]] = None) -> float:
    if primes_soumises_impot is None:
        primes_soumises_impot = []
    
    print("\n--- Calcul du Net À Payer ---", file=sys.stderr)
    print(f"\t  Net Social (base de départ)      : {net_social:10.2f} €", file=sys.stderr)
    print(f"\t- Impôt sur le revenu              : {montant_pas:10.2f} €", file=sys.stderr)
    
    net_apres_impot = _get_safe_float(net_social) - _get_safe_float(montant_pas)
    print("\t--------------------------------------------", file=sys.stderr)
    print(f"\t= Net après impôt                  : {net_apres_impot:10.2f} €", file=sys.stderr)

    # Initialisation du net à payer
    net_a_payer = net_apres_impot
    
    # Déduction des titres-restaurant
    tr_spec = contexte.contrat.get('specificites_paie', {}).get('titres_restaurant', {})
    if tr_spec.get('beneficie'):
        valeur_faciale = _get_safe_float(tr_spec.get('valeur_faciale'))
        part_patronale = _get_safe_float(tr_spec.get('part_patronale'))
        nombre_tr = _get_safe_float(tr_spec.get('nombre_par_mois'))
        part_salariale_tr = valeur_faciale - part_patronale
        deduction_tr = part_salariale_tr * nombre_tr
        
        print(f"\t- Déduction Titres-Restaurant      : {deduction_tr:10.2f} €", file=sys.stderr)
        net_a_payer -= deduction_tr
    
    # Ajout du remboursement transport
    transport_spec = contexte.contrat.get('specificites_paie', {}).get('transport', {})
    cout_total_abonnement = _get_safe_float(transport_spec.get('abonnement_mensuel_total', 0.0))
    remboursement_transport = 0.0
    
    if cout_total_abonnement > 0:
        remboursement_transport = round(cout_total_abonnement * 0.5, 2)
        print(f"\t+ Remboursement Transport          : {remboursement_transport:10.2f} €", file=sys.stderr)
        net_a_payer += remboursement_transport
    
    # Ajout des primes non soumises aux cotisations ni à l'impôt
    montant_primes_non_soumises = 0.0
    for prime in primes_non_soumises:
        montant_prime = _get_safe_float(prime.get('montant'))
        montant_primes_non_soumises += montant_prime
        
    if montant_primes_non_soumises > 0:
        print(f"\t+ Primes non soumises              : {montant_primes_non_soumises:10.2f} €", file=sys.stderr)
        net_a_payer += montant_primes_non_soumises
    
    # --- NOUVEAU : Ajout des primes soumises à l'impôt (non soumises aux cotisations) ---
    # Ces primes ne sont pas dans le brut car non soumises aux cotisations, mais doivent être dans le net à payer
    montant_primes_soumises_impot = 0.0
    for prime in primes_soumises_impot:
        montant_prime = _get_safe_float(prime.get('montant'))
        montant_primes_soumises_impot += montant_prime
    
    if montant_primes_soumises_impot > 0:
        print(f"\t+ Primes soumises à l'impôt        : {montant_primes_soumises_impot:10.2f} €", file=sys.stderr)
        net_a_payer += montant_primes_soumises_impot

    if montant_acompte > 0:
        print(f"\t- Acompte versé                    : {montant_acompte:10.2f} €", file=sys.stderr)
        net_a_payer -= montant_acompte
    print("\t--------------------------------------------", file=sys.stderr)
    print(f"\t= NET À PAYER                      : {round(net_a_payer, 2):10.2f} €", file=sys.stderr)
    print("-----------------------------\n", file=sys.stderr)

    return round(net_a_payer, 2), remboursement_transport


def calculer_net_et_impot(
    contexte: ContextePaie,
    salaire_brut: float,
    lignes_cotisations: List[Dict[str, Any]],
    total_cotisations_salariales: float,
    primes_non_soumises: List[Dict[str, Any]],
    remuneration_heures_supp: float,
    montant_acompte: float = 0.0,
    primes_soumises_impot: List[Dict[str, Any]] = None # <-- NOUVEAU: Primes soumises à l'impôt (ex: PPV si effectif >= 50)
) -> Dict[str, float]:
    if primes_soumises_impot is None:
        primes_soumises_impot = []
    
    print("INFO: Démarrage du calcul des nets et de l'impôt...", file=sys.stderr)
    
    net_social = round(_get_safe_float(salaire_brut) - _get_safe_float(total_cotisations_salariales), 2)
    
    # MODIFIÉ: On passe la nouvelle variable à la fonction de calcul
    net_imposable = _calculer_net_imposable(
        contexte, 
        salaire_brut, 
        total_cotisations_salariales, 
        lignes_cotisations,
        remuneration_heures_supp,
        primes_soumises_impot  # <-- NOUVEAU: Primes soumises à l'impôt
    )
    
    montant_impot = _calculer_prelevement_a_la_source(contexte, net_imposable)
    net_a_payer, remboursement_transport = _calculer_net_a_payer(
        net_social, 
        montant_impot, 
        contexte, 
        primes_non_soumises,
        montant_acompte,  # <--- AJOUTEZ L'ARGUMENT ICI
        primes_soumises_impot  # <-- NOUVEAU: Primes soumises à l'impôt
    )
    print("INFO: Calcul des nets et de l'impôt terminé.", file=sys.stderr)
    return {
        "net_social": net_social, 
        "net_imposable": net_imposable, 
        "montant_impot_pas": montant_impot, 
        "net_a_payer": net_a_payer,
        "remboursement_transport": remboursement_transport,
        "acompte_verse": montant_acompte # <--- AJOUTEZ CETTE LIGNE
    }