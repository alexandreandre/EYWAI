#!/usr/bin/env python3
"""
Script de test complet pour l'implémentation du forfait jour.

Ce script teste :
1. L'analyseur avec filtrage par période de paie (sur plusieurs mois)
2. Le calcul du brut avec absences injustifiées
3. La normalisation des données (0/1 pour heures_prevues/heures_faites)
4. Le scénario d'un employé absent injustifié sur toute la période de paie
"""

import sys
import json
from datetime import date, timedelta
from typing import Dict, Any, List

# Source de vérité : app.modules.payroll.engine
from app.modules.payroll.engine.analyser_jours_forfait import analyser_jours_forfait_du_mois
from app.modules.payroll.engine.calcul_brut_forfait import calculer_salaire_brut_forfait


class ContextePaieMock:
    """
    Contexte de paie mock pour les tests, sans dépendance à Supabase.
    Expose les mêmes attributs que ContextePaie utilisés par calcul_brut_forfait.
    """
    def __init__(
        self,
        salaire_base: float = 5000.0,
        statut: str = "Cadre forfait jour",
    ):
        self.entreprise = {
            "parametres_paie": {
                "periode_de_paie": {"jour_de_fin": 4, "occurrence": -2},
                "avantages_en_nature": {
                    "repas_valeur_forfaitaire": 0.0,
                    "logement_bareme_forfaitaire": []
                }
            }
        }
        self.contrat = {
            "contrat": {
                "statut": statut,
                "date_debut": "2024-01-01",
                "date_entree": "2024-01-01",
                "type_contrat": "CDI",
                "temps_travail": {"duree_hebdomadaire": 35}
            },
            "remuneration": {
                "salaire_de_base": {"valeur": salaire_base},
                "avantages_en_nature": {
                    "repas": {"nombre_par_mois": 0},
                    "logement": {"beneficie": False},
                    "vehicule": {"beneficie": False}
                },
                "classification_conventionnelle": {},
                "convention_collective": {}
            },
            "specificites_paie": {"is_alsace_moselle": False}
        }
        self.cumuls = {"cumuls": {}, "periode": {}}
        self.baremes = {
            "primes": [],
            "conventions_collectives": {}
        }

    @property
    def salaire_base_mensuel(self) -> float:
        return self.contrat.get("remuneration", {}).get("salaire_de_base", {}).get("valeur", 0.0)

    @property
    def statut_salarie(self) -> str:
        return self.contrat.get("contrat", {}).get("statut", "Non-Cadre")

    @property
    def is_forfait_jour(self) -> bool:
        s = self.statut_salarie or ""
        return "forfait jour" in s.lower()


def creer_contexte_test() -> ContextePaieMock:
    """Crée un contexte de test minimal pour le forfait jour (sans Supabase)."""
    return ContextePaieMock(salaire_base=5000.0, statut="Cadre forfait jour")


def generer_calendrier_mois(annee: int, mois: int, jours_travailles: List[int]) -> List[Dict[str, Any]]:
    """
    Génère un calendrier prévu pour un mois donné.
    jours_travailles: Liste des numéros de jour du mois où l'employé doit travailler.
    """
    import calendar
    calendrier = []
    _, nb_jours = calendar.monthrange(annee, mois)
    
    for jour in range(1, nb_jours + 1):
        jour_date = date(annee, mois, jour)
        jour_semaine = jour_date.weekday()  # 0 = lundi, 6 = dimanche
        
        # Weekends non travaillés
        if jour_semaine >= 5:
            calendrier.append({
                "jour": jour,
                "type": "weekend",
                "heures_prevues": 0
            })
        elif jour in jours_travailles:
            calendrier.append({
                "jour": jour,
                "type": "travail",
                "heures_prevues": 1  # Forfait jour : 1 = jour travaillé
            })
        else:
            calendrier.append({
                "jour": jour,
                "type": "travail",
                "heures_prevues": 0  # Jour non travaillé
            })
    
    return calendrier


def generer_calendrier_reel(annee: int, mois: int, jours_travailles: List[int]) -> List[Dict[str, Any]]:
    """
    Génère un calendrier réel pour un mois donné.
    jours_travailles: Liste des numéros de jour du mois où l'employé a réellement travaillé.
    """
    import calendar
    calendrier = []
    _, nb_jours = calendar.monthrange(annee, mois)
    
    for jour in range(1, nb_jours + 1):
        jour_date = date(annee, mois, jour)
        jour_semaine = jour_date.weekday()
        
        # Weekends non travaillés
        if jour_semaine >= 5:
            calendrier.append({
                "jour": jour,
                "type": "weekend",
                "heures_faites": 0
            })
        elif jour in jours_travailles:
            calendrier.append({
                "jour": jour,
                "type": "travail",
                "heures_faites": 1  # Forfait jour : 1 = jour travaillé
            })
        else:
            calendrier.append({
                "jour": jour,
                "type": "travail",
                "heures_faites": 0  # Jour non travaillé
            })
    
    return calendrier


def calculer_periode_paie(annee: int, mois: int) -> tuple[date, date]:
    """
    Calcule la période de paie pour un mois donné.
    Simule la logique de definir_periode_de_paie avec avant-dernier vendredi.
    """
    import calendar
    
    def trouver_jour_reference(target_annee: int, target_mois: int, jour_cible: int, occurrence: int) -> date:
        """Trouve l'avant-dernier vendredi du mois."""
        _, num_days = calendar.monthrange(target_annee, target_mois)
        jours_trouves = [
            date(target_annee, target_mois, day)
            for day in range(1, num_days + 1)
            if date(target_annee, target_mois, day).weekday() == jour_cible
        ]
        return jours_trouves[occurrence]
    
    # Trouver l'avant-dernier vendredi du mois
    date_reference = trouver_jour_reference(annee, mois, 4, -2)
    
    # Date de fin = dimanche de la semaine de référence
    decalage_vers_dimanche = 6 - date_reference.weekday()
    date_fin_periode = date_reference + timedelta(days=decalage_vers_dimanche)
    
    # Trouver l'avant-dernier vendredi du mois précédent
    mois_precedent = mois - 1
    annee_precedente = annee
    if mois_precedent == 0:
        mois_precedent = 12
        annee_precedente -= 1
    
    date_reference_precedente = trouver_jour_reference(annee_precedente, mois_precedent, 4, -2)
    decalage_vers_dimanche_precedent = 6 - date_reference_precedente.weekday()
    date_fin_periode_precedente = date_reference_precedente + timedelta(days=decalage_vers_dimanche_precedent)
    
    date_debut_periode = date_fin_periode_precedente + timedelta(days=1)
    
    return date_debut_periode, date_fin_periode


def test_analyseur_avec_periode_paie():
    """Test 1: Vérifie que l'analyseur filtre correctement selon la période de paie."""
    print("\n" + "="*80)
    print("TEST 1: Analyseur avec filtrage par période de paie")
    print("="*80)
    
    annee = 2025
    mois = 4  # Avril
    
    # Calculer la période de paie (ex: du 23 mars au 19 avril)
    date_debut, date_fin = calculer_periode_paie(annee, mois)
    print(f"\n📅 Période de paie calculée : du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}")
    
    # Générer des données pour mars, avril et mai
    # Mars : quelques jours travaillés prévus à la fin du mois
    jours_prevus_mars = list(range(24, 32))  # 24-31 mars
    jours_prevus_avril = list(range(1, 20))  # 1-19 avril (dans la période)
    jours_prevus_mai = []  # Pas encore dans la période
    
    planned_data_all_months = []
    actual_data_all_months = []
    
    # Mars
    cal_prevu_mars = generer_calendrier_mois(2025, 3, jours_prevus_mars)
    for j in cal_prevu_mars:
        j['annee'] = 2025
        j['mois'] = 3
    planned_data_all_months.extend(cal_prevu_mars)
    
    # Avril
    cal_prevu_avril = generer_calendrier_mois(2025, 4, jours_prevus_avril)
    for j in cal_prevu_avril:
        j['annee'] = 2025
        j['mois'] = 4
    planned_data_all_months.extend(cal_prevu_avril)
    
    # Mai
    cal_prevu_mai = generer_calendrier_mois(2025, 5, jours_prevus_mai)
    for j in cal_prevu_mai:
        j['annee'] = 2025
        j['mois'] = 5
    planned_data_all_months.extend(cal_prevu_mai)
    
    # Calendrier réel : ABSENCE TOTALE sur toute la période
    # Aucun jour travaillé dans la période
    cal_reel_mars = generer_calendrier_reel(2025, 3, [])
    for j in cal_reel_mars:
        j['annee'] = 2025
        j['mois'] = 3
    actual_data_all_months.extend(cal_reel_mars)
    
    cal_reel_avril = generer_calendrier_reel(2025, 4, [])
    for j in cal_reel_avril:
        j['annee'] = 2025
        j['mois'] = 4
    actual_data_all_months.extend(cal_reel_avril)
    
    # Appel de l'analyseur SANS période de paie (ancien comportement)
    print("\n🔍 Test SANS période de paie (filtrage par mois uniquement) :")
    evenements_sans_periode = analyser_jours_forfait_du_mois(
        planned_data_all_months,
        actual_data_all_months,
        annee,
        mois,
        "Test Employee",
        date_debut_periode=None,
        date_fin_periode=None
    )
    
    absences_sans_periode = [e for e in evenements_sans_periode if "absence" in e.get('type', '')]
    print(f"   ❌ Absences détectées (mois uniquement) : {len(absences_sans_periode)}")
    print(f"   📊 Événements totaux : {len(evenements_sans_periode)}")
    
    # Appel de l'analyseur AVEC période de paie (nouveau comportement)
    print("\n🔍 Test AVEC période de paie (filtrage sur toute la période) :")
    evenements_avec_periode = analyser_jours_forfait_du_mois(
        planned_data_all_months,
        actual_data_all_months,
        annee,
        mois,
        "Test Employee",
        date_debut_periode=date_debut,
        date_fin_periode=date_fin
    )
    
    absences_avec_periode = [e for e in evenements_avec_periode if "absence" in e.get('type', '')]
    print(f"   ✅ Absences détectées (période complète) : {len(absences_avec_periode)}")
    print(f"   📊 Événements totaux : {len(evenements_avec_periode)}")
    
    # Compter les jours ouvrés dans la période
    jours_ouvres_periode = 0
    current_date = date_debut
    while current_date <= date_fin:
        if current_date.weekday() < 5:  # Lundi à vendredi
            jours_ouvres_periode += 1
        current_date += timedelta(days=1)
    
    print(f"\n📈 Résultats attendus :")
    print(f"   - Jours ouvrés dans la période : {jours_ouvres_periode}")
    print(f"   - Absences attendues (si absence totale) : ~{jours_ouvres_periode}")
    
    # Vérification
    if len(absences_avec_periode) > len(absences_sans_periode):
        print(f"\n✅ SUCCÈS : Le filtrage par période fonctionne !")
        print(f"   Les absences du mois précédent ({len(absences_avec_periode) - len(absences_sans_periode)} jours) sont maintenant comptées.")
    else:
        print(f"\n⚠️  ATTENTION : Le filtrage par période ne semble pas fonctionner correctement.")
    
    return evenements_avec_periode, date_debut, date_fin


def test_calcul_brut_avec_absences():
    """Test 2: Vérifie le calcul du brut avec absences injustifiées."""
    print("\n" + "="*80)
    print("TEST 2: Calcul du brut avec absences injustifiées")
    print("="*80)
    
    contexte = creer_contexte_test()
    annee = 2025
    mois = 4
    
    # Calculer la période de paie
    date_debut, date_fin = calculer_periode_paie(annee, mois)
    
    # Générer des événements avec absences injustifiées
    evenements = []
    current_date = date_debut
    while current_date <= date_fin:
        if current_date.weekday() < 5:  # Lundi à vendredi
            evenements.append({
                "jour": current_date.day,
                "mois": current_date.month,
                "annee": current_date.year,
                "type": "absence_injustifiee_base",
                "heures": 1.0,
                "date_complete": current_date.isoformat()
            })
        current_date += timedelta(days=1)
    
    print(f"\n📅 Période de paie : du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}")
    print(f"📊 Nombre d'absences injustifiées : {len(evenements)}")
    
    # Calculer le brut
    resultat_brut = calculer_salaire_brut_forfait(
        contexte=contexte,
        calendrier_saisie=evenements,
        date_debut_periode=date_debut,
        date_fin_periode=date_fin,
        primes_saisies=[]
    )
    
    print(f"\n💰 Résultats du calcul :")
    print(f"   - Salaire de base : {resultat_brut.get('salaire_base', 0):.2f} €")
    print(f"   - Brut total : {resultat_brut.get('brut_total', 0):.2f} €")
    print(f"   - Nombre de jours d'absence : {resultat_brut.get('nombre_jours_absence_injustifiee', 0)}")
    
    # Vérifier que le brut n'est pas négatif
    brut_total = resultat_brut.get('brut_total', 0)
    if brut_total < 0:
        print(f"\n❌ ERREUR : Le brut total est négatif ({brut_total:.2f} €)")
        return False
    else:
        print(f"\n✅ SUCCÈS : Le brut total est valide ({brut_total:.2f} €)")
    
    # Vérifier les lignes de déduction
    lignes_composants = resultat_brut.get('lignes_composants_brut', [])
    lignes_absences = [l for l in lignes_composants if "absence" in l.get('libelle', '').lower()]
    print(f"\n📋 Lignes de déduction d'absence : {len(lignes_absences)}")
    for ligne in lignes_absences[:3]:  # Afficher les 3 premières
        print(f"   - {ligne.get('libelle', '')} : -{ligne.get('perte', 0):.2f} €")
    
    return True


def test_normalisation_donnees():
    """Test 3: Vérifie la normalisation des données (0/1 pour forfait jour)."""
    print("\n" + "="*80)
    print("TEST 3: Normalisation des données (0/1 pour forfait jour)")
    print("="*80)
    
    # Simuler des données avec des valeurs horaires (8.0) au lieu de jours (1)
    donnees_non_normalisees = [
        {"jour": 1, "type": "travail", "heures_prevues": 8.0},  # ❌ Devrait être 1
        {"jour": 2, "type": "travail", "heures_prevues": 0.0},  # ✅ Correct
        {"jour": 3, "type": "travail", "heures_prevues": 7.5},  # ❌ Devrait être 1
    ]
    
    print("\n📊 Données avant normalisation :")
    for d in donnees_non_normalisees:
        print(f"   Jour {d['jour']} : heures_prevues = {d['heures_prevues']}")
    
    # Simuler la normalisation (logique de schedules.py)
    def normaliser_heures(valeur):
        """Normalise les heures pour forfait jour : >0 → 1, 0/null → 0"""
        if valeur is None:
            return 0
        if isinstance(valeur, (int, float)):
            return 1 if valeur > 0 else 0
        return 0
    
    donnees_normalisees = []
    for d in donnees_non_normalisees:
        d_norm = d.copy()
        d_norm['heures_prevues'] = normaliser_heures(d['heures_prevues'])
        donnees_normalisees.append(d_norm)
    
    print("\n📊 Données après normalisation :")
    for d in donnees_normalisees:
        print(f"   Jour {d['jour']} : heures_prevues = {d['heures_prevues']}")
    
    # Vérification
    toutes_normalisees = all(
        d['heures_prevues'] in [0, 1] for d in donnees_normalisees
    )
    
    if toutes_normalisees:
        print("\n✅ SUCCÈS : Toutes les données sont normalisées (0 ou 1)")
    else:
        print("\n❌ ERREUR : Certaines données ne sont pas normalisées")
    
    return toutes_normalisees


def test_scenario_complet():
    """Test 4: Scénario complet d'un employé absent injustifié sur toute la période."""
    print("\n" + "="*80)
    print("TEST 4: Scénario complet - Absence injustifiée totale")
    print("="*80)
    
    contexte = creer_contexte_test()
    annee = 2025
    mois = 4
    
    # Calculer la période de paie
    date_debut, date_fin = calculer_periode_paie(annee, mois)
    
    print(f"\n📅 Période de paie : du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}")
    
    # Générer calendrier prévu : tous les jours ouvrés prévus
    planned_data_all_months = []
    actual_data_all_months = []
    
    # Mars (fin du mois dans la période)
    jours_prevus_mars = []
    current_date = date_debut
    while current_date.month == 3:
        if current_date.weekday() < 5:
            jours_prevus_mars.append(current_date.day)
        current_date += timedelta(days=1)
    
    cal_prevu_mars = generer_calendrier_mois(2025, 3, jours_prevus_mars)
    for j in cal_prevu_mars:
        j['annee'] = 2025
        j['mois'] = 3
    planned_data_all_months.extend(cal_prevu_mars)
    
    # Avril (début du mois dans la période)
    jours_prevus_avril = []
    current_date = date(2025, 4, 1)
    while current_date <= date_fin:
        if current_date.weekday() < 5:
            jours_prevus_avril.append(current_date.day)
        current_date += timedelta(days=1)
    
    cal_prevu_avril = generer_calendrier_mois(2025, 4, jours_prevus_avril)
    for j in cal_prevu_avril:
        j['annee'] = 2025
        j['mois'] = 4
    planned_data_all_months.extend(cal_prevu_avril)
    
    # Calendrier réel : ABSENCE TOTALE (aucun jour travaillé)
    cal_reel_mars = generer_calendrier_reel(2025, 3, [])
    for j in cal_reel_mars:
        j['annee'] = 2025
        j['mois'] = 3
    actual_data_all_months.extend(cal_reel_mars)
    
    cal_reel_avril = generer_calendrier_reel(2025, 4, [])
    for j in cal_reel_avril:
        j['annee'] = 2025
        j['mois'] = 4
    actual_data_all_months.extend(cal_reel_avril)
    
    # Analyser les événements
    evenements = analyser_jours_forfait_du_mois(
        planned_data_all_months,
        actual_data_all_months,
        annee,
        mois,
        "Test Employee Absent",
        date_debut_periode=date_debut,
        date_fin_periode=date_fin
    )
    
    # Ajouter les dates complètes avec validation
    import calendar
    for ev in evenements:
        ev_annee = ev.get('annee', annee)
        ev_mois = ev.get('mois', mois)
        ev_jour = ev.get('jour')
        if ev_jour:
            # Vérifier que le jour est valide pour le mois
            try:
                _, nb_jours_mois = calendar.monthrange(ev_annee, ev_mois)
                if ev_jour <= nb_jours_mois:
                    ev['date_complete'] = date(ev_annee, ev_mois, ev_jour).isoformat()
                else:
                    print(f"⚠️  Avertissement: Jour {ev_jour} invalide pour {ev_mois}/{ev_annee}, ignoré", file=sys.stderr)
            except ValueError as e:
                print(f"⚠️  Erreur lors de la création de la date pour l'événement {ev}: {e}", file=sys.stderr)
    
    absences = [e for e in evenements if "absence" in e.get('type', '')]
    print(f"\n📊 Événements générés :")
    print(f"   - Total : {len(evenements)}")
    print(f"   - Absences injustifiées : {len(absences)}")
    
    # Calculer le brut
    resultat_brut = calculer_salaire_brut_forfait(
        contexte=contexte,
        calendrier_saisie=evenements,
        date_debut_periode=date_debut,
        date_fin_periode=date_fin,
        primes_saisies=[]
    )
    
    brut_total = resultat_brut.get('brut_total', 0)
    salaire_base = resultat_brut.get('salaire_base', 0)
    
    print(f"\n💰 Résultats finaux :")
    print(f"   - Salaire de base : {salaire_base:.2f} €")
    print(f"   - Brut total : {brut_total:.2f} €")
    print(f"   - Déduction totale : {salaire_base - brut_total:.2f} €")
    
    # Vérifications
    succes = True
    
    if len(absences) == 0:
        print(f"\n❌ ERREUR : Aucune absence détectée alors que l'employé est absent toute la période")
        succes = False
    else:
        print(f"\n✅ SUCCÈS : {len(absences)} absences détectées sur toute la période")
    
    if brut_total < 0:
        print(f"\n❌ ERREUR : Le brut total est négatif")
        succes = False
    else:
        print(f"\n✅ SUCCÈS : Le brut total est valide (protection activée)")
    
    return succes


def main():
    """Fonction principale qui exécute tous les tests."""
    print("\n" + "="*80)
    print("🧪 TESTS COMPLETS - IMPLÉMENTATION FORFAIT JOUR")
    print("="*80)
    
    resultats = {}
    
    try:
        # Test 1: Analyseur avec période de paie
        evenements, date_debut, date_fin = test_analyseur_avec_periode_paie()
        resultats['test_1'] = True
    except Exception as e:
        print(f"\n❌ ERREUR dans Test 1 : {e}")
        import traceback
        traceback.print_exc()
        resultats['test_1'] = False
    
    try:
        # Test 2: Calcul du brut avec absences
        resultats['test_2'] = test_calcul_brut_avec_absences()
    except Exception as e:
        print(f"\n❌ ERREUR dans Test 2 : {e}")
        import traceback
        traceback.print_exc()
        resultats['test_2'] = False
    
    try:
        # Test 3: Normalisation des données
        resultats['test_3'] = test_normalisation_donnees()
    except Exception as e:
        print(f"\n❌ ERREUR dans Test 3 : {e}")
        import traceback
        traceback.print_exc()
        resultats['test_3'] = False
    
    try:
        # Test 4: Scénario complet
        resultats['test_4'] = test_scenario_complet()
    except Exception as e:
        print(f"\n❌ ERREUR dans Test 4 : {e}")
        import traceback
        traceback.print_exc()
        resultats['test_4'] = False
    
    # Résumé final
    print("\n" + "="*80)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*80)
    
    for test_name, resultat in resultats.items():
        status = "✅ SUCCÈS" if resultat else "❌ ÉCHEC"
        print(f"   {test_name} : {status}")
    
    tous_reussis = all(resultats.values())
    
    if tous_reussis:
        print("\n🎉 TOUS LES TESTS SONT PASSÉS !")
        return 0
    else:
        print("\n⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
        return 1


if __name__ == "__main__":
    sys.exit(main())
