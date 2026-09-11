from app.core.logging import get_logger

logger = get_logger("modules.payroll.engine.calcul_brut_forfait")
# moteur_paie/calcul_brut_forfait.py
"""
Module de calcul du salaire brut pour les employés en forfait jour.

Le forfait jour fonctionne différemment du mode horaire :
- Pas d'heures supplémentaires (forfait annuel)
- Salaire généralement fixe
- Absences déduites en jours, pas en heures
- Pas de calcul de taux horaire
"""

from .contexte import ContextePaie
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from app.shared.domain.employment_rules import is_cadre
from .calcul_conges import calculer_indemnite_conges
from .calcul_brut import (
    _format_jours_conges,
    _jour_ferie_est_paye,
    _jours_evenement_conges,
    _libelle_dates_conges,
)

# Jours ouvrés moyens par mois (261 j / 12) : valorisation d'une journée de
# forfait, à défaut d'un paramètre société `forfait_jours_ouvres_mois`.
JOURS_OUVRES_MOYENS_MOIS = 21.67


def _diviseur_jour_absence(contexte: ContextePaie) -> float:
    """Nombre de jours ouvrés retenu pour valoriser UNE journée d'absence en
    forfait jour (arrêt, absence non rémunérée, férié non payé).

    Convention de paie, pas règle légale : 21,67 (moyenne légale) par défaut,
    un cabinet peut retenir 22 (`companies.settings.forfait_jours_ouvres_mois`).
    Les congés payés restent valorisés sur la moyenne 21,67 (méthode du
    maintien), quel que soit ce paramètre.
    """
    brut = (contexte.entreprise.get("parametres_paie", {}) or {}).get(
        "forfait_jours_ouvres_mois"
    )
    try:
        valeur = float(brut) if brut is not None else 0.0
    except (TypeError, ValueError):
        valeur = 0.0
    return valeur if valeur > 0 else JOURS_OUVRES_MOYENS_MOIS
from .salary_evolution_brut import (
    lignes_rappel_salaire,
    salaire_contractuel_avec_evolution,
)


def _construire_ligne_avantages_en_nature(
    contexte: ContextePaie,
) -> Dict[str, Any] | None:
    """
    Construit la ligne d'avantages en nature (identique au mode horaire).
    """
    total_avantages = 0.0
    regles_aen = contexte.entreprise.get("parametres_paie", {}).get(
        "avantages_en_nature", {}
    ) or {}
    situation_salarie_aen = contexte.contrat.get("remuneration", {}).get(
        "avantages_en_nature", {}
    ) or {}

    situation_repas = situation_salarie_aen.get("repas", {})
    if situation_repas.get("nombre_par_mois", 0) > 0:
        valeur_forfaitaire_repas = regles_aen.get("repas_valeur_forfaitaire", 0.0)
        total_avantages += situation_repas["nombre_par_mois"] * valeur_forfaitaire_repas

    situation_logement = situation_salarie_aen.get("logement", {})
    if situation_logement.get("beneficie"):
        bareme_logement = regles_aen.get("logement_bareme_forfaitaire", [])
        salaire_mensuel = contexte.salaire_base_mensuel
        nb_pieces = situation_logement.get("nombre_pieces_principales", 1)
        for tranche in bareme_logement:
            if salaire_mensuel <= tranche.get("remuneration_max", float("inf")):
                valeur = tranche["valeur_1_piece"]
                if nb_pieces > 1:
                    valeur += tranche["valeur_par_piece"] * (nb_pieces - 1)
                total_avantages += valeur
                break

    situation_pret = situation_salarie_aen.get("pret_employeur", {})
    if isinstance(situation_pret, dict):
        montant_pret = situation_pret.get("montant_mensuel", 0) or 0
        if montant_pret > 0:
            total_avantages += float(montant_pret)

    if total_avantages > 0:
        return {
            "libelle": "Avantages en nature",
            "quantite": None,
            "taux": None,
            "gain": round(total_avantages, 2),
            "perte": None,
        }
    return None


def _calculer_prime_anciennete(
    contexte: ContextePaie,
    *,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    jours_maintien: Optional[set[int]] = None,
    actual_hours_raw: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any] | None:
    # La prime d'ancienneté de la CCN plasturgie (IDCC 292) est réservée aux
    # non-cadres (ouvriers/employés/techniciens). Les salariés en forfait jour
    # cadres n'y ont pas droit — les bulletins Cegid ne la portent pas
    # (cf. LABBE/DROZ/GILLET/BORDELIER/BLONDEAU mai 2026 : base = brut exact,
    # sans ligne prime d'ancienneté).
    if is_cadre(contexte.statut_salarie):
        return None

    from app.modules.payroll.engine.prime_anciennete import calculer_ligne_prime_anciennete

    ligne = calculer_ligne_prime_anciennete(
        contexte,
        calendrier_saisie=calendrier_saisie,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        jours_maintien=jours_maintien,
        actual_hours_raw=actual_hours_raw,
    )
    if not ligne:
        return None
    ligne.pop("meta", None)
    return ligne


def _jours_evenement_absence(evenement: Dict[str, Any]) -> float:
    """Jours imputés sur un jour d'absence en forfait jour.

    En forfait jour l'unité portante est le JOUR (`heures = 1` signifie 1 jour) :
    un jour d'arrêt est posé `heures_prevues=0` — côté horaire c'est le signal
    d'imputer la journée entière (`calcul_brut._heures_evenement_absence` replie
    sur la référence journalière légale), ici il vaut donc 1 jour. Le plafond à 1
    garantit qu'un jour calendaire ne peut jamais coûter plus d'une journée de
    forfait, même si la quantité du jour a été saisie en heures (7,0/7,5) par un
    template horaire.
    """
    heures = evenement.get("heures")
    if heures is None or heures == 0:
        return 1.0
    return min(float(heures), 1.0)


def _calculer_deduction_absence_forfait_jour(
    contexte: ContextePaie, nombre_jours_absence: int, salaire_journalier: float
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
        "perte": montant_deduction,
    }


def calculer_salaire_brut_forfait(
    contexte: ContextePaie,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    primes_saisies: List[Dict[str, Any]] = None,
    jours_maintien: Optional[set[int]] = None,
    actual_hours_raw: Optional[List[Dict[str, Any]]] = None,
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
    salaire_contractuel = salaire_contractuel_avec_evolution(
        contexte, contexte.salaire_base_mensuel
    )

    # Salaire journalier : moyenne légale 21,67 j (261 j / 12) pour les congés
    # payés (méthode du maintien) ; les autres absences se valorisent sur le
    # diviseur société (21,67 par défaut, 22 chez certains cabinets).
    jours_ouvres_moyens_mois = JOURS_OUVRES_MOYENS_MOIS
    salaire_journalier = salaire_contractuel / jours_ouvres_moyens_mois
    salaire_journalier_absence = salaire_contractuel / _diviseur_jour_absence(contexte)

    # 1. Salaire de base (forfait mensuel)
    lignes_composants_brut.append(
        {
            "libelle": "Salaire de base (forfait jour)",
            "quantite": None,
            "taux": None,
            "gain": round(salaire_contractuel, 2),
            "perte": None,
        }
    )

    contrat = contexte.contrat.get("contrat", {}) or {}
    try:
        date_entree = date.fromisoformat(str(contrat.get("date_entree"))[:10])
    except (TypeError, ValueError):
        date_entree = None
    try:
        date_sortie = date.fromisoformat(
            str(contrat.get("date_sortie") or contrat.get("date_fin_contrat"))[:10]
        )
    except (TypeError, ValueError):
        date_sortie = None

    jours_ouvres_mois = [
        date_debut_periode + timedelta(days=offset)
        for offset in range((date_fin_periode - date_debut_periode).days + 1)
        if (date_debut_periode + timedelta(days=offset)).weekday() < 5
    ]
    # Entré dès le premier jour ouvré (hors férié) du mois = présent tout le
    # mois : aucun prorata d'entrée. Un férié chômé avant l'embauche n'est pas
    # un jour perdu (SMITH MAJI, entré le lundi 04/05/2026 après le 1er mai :
    # salaire plein chez le cabinet).
    feries_periode = {
        date.fromisoformat(j["date_complete"])
        for j in calendrier_saisie
        if j.get("type") == "ferie" and j.get("date_complete")
    }
    premier_jour_ouvre = next(
        (jour for jour in jours_ouvres_mois if jour not in feries_periode), None
    )
    if date_entree and premier_jour_ouvre and date_entree <= premier_jour_ouvre:
        date_entree_effective = None
    else:
        date_entree_effective = date_entree
    jours_hors_contrat = [
        jour
        for jour in jours_ouvres_mois
        if (date_entree_effective and jour < date_entree_effective)
        or (date_sortie and jour > date_sortie)
    ]
    if jours_hors_contrat and jours_ouvres_mois:
        taux_prorata = salaire_contractuel / len(jours_ouvres_mois)
        lignes_composants_brut.append(
            {
                "libelle": "Absence pour entrée ou sortie",
                "quantite": float(len(jours_hors_contrat)),
                "taux": round(taux_prorata, 4),
                "gain": None,
                "perte": round(len(jours_hors_contrat) * taux_prorata, 2),
                "is_entree_sortie": True,
            }
        )

    # 2. Traitement des événements de la période
    jours_dans_periode = [
        j
        for j in calendrier_saisie
        if "date_complete" in j
        and date_debut_periode
        <= date.fromisoformat(j["date_complete"])
        <= date_fin_periode
    ]

    jours_conges_dans_periode = []
    nombre_jours_absence_injustifiee = 0
    nombre_jours_travailles = 0
    # Journées retenues (arrêt, non rémunérée, injustifiée, férié non payé) :
    # sert à reconnaître un mois entièrement absent.
    jours_absence_non_payes = 0.0

    jours_hors_contrat_set = set(jours_hors_contrat)
    for evenement in jours_dans_periode:
        type_ev = evenement.get("type", "")
        heures = evenement.get("heures", 0.0)
        # Un jour avant l'entrée ou après la sortie est déjà retenu par le
        # prorata d'entrée/sortie : un férié ou une absence posés sur ce jour
        # ne doivent pas être retenus une seconde fois (FILLINGER Zone 404,
        # entré le 27/04 : lundi de Pâques 06/04 retenu deux fois).
        try:
            if date.fromisoformat(evenement["date_complete"]) in jours_hors_contrat_set:
                continue
        except (KeyError, TypeError, ValueError):
            pass

        # En forfait jour, heures = 1 signifie "1 jour"
        if type_ev == "travail_base":
            nombre_jours_travailles += heures
        elif type_ev == "conges_payes":
            jours_conges_dans_periode.append(evenement)
        elif "absence_injustifiee" in type_ev:
            # Un jour calendaire coûte au plus UNE journée de forfait : le jour
            # posé porte souvent 7 h / 7,8 h « prévues » (gabarit horaire), qui
            # valaient ici 7,8 journées et vidaient le brut (ASSANHAJI Zone 404
            # 03/2026 : 5 j d'absence non rémunérée → brut 0 au lieu de 2 788).
            jours_abs = _jours_evenement_absence(evenement)
            nombre_jours_absence_injustifiee += jours_abs
            jours_absence_non_payes += jours_abs
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            montant_deduction = round(jours_abs * salaire_journalier_absence, 2)
            lignes_composants_brut.append(
                {
                    "libelle": f"Absence injustifiée du {date_absence} ({_format_jours_conges(jours_abs)} jour{'s' if jours_abs > 1 else ''})",
                    "quantite": jours_abs,
                    "taux": round(salaire_journalier_absence, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )
        elif type_ev == "absence_non_remuneree":
            jours_abs = _jours_evenement_absence(evenement)
            nombre_jours_absence_injustifiee += jours_abs
            jours_absence_non_payes += jours_abs
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            montant_deduction = round(jours_abs * salaire_journalier_absence, 2)
            lignes_composants_brut.append(
                {
                    "libelle": f"Absence non rémunérée du {date_absence} ({_format_jours_conges(jours_abs)} jour{'s' if jours_abs > 1 else ''})",
                    "quantite": jours_abs,
                    "taux": round(salaire_journalier_absence, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )
        elif type_ev == "ferie" and not _jour_ferie_est_paye(contexte, evenement):
            # Férié chômé non payé (ancienneté < 3 mois, art. L3133-3) : même
            # règle qu'en mode horaire, une journée de forfait retenue.
            jours_abs = 1.0
            jours_absence_non_payes += jours_abs
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Abs. jour férié non payé du {date_absence}",
                    "quantite": jours_abs,
                    "taux": round(salaire_journalier_absence, 4),
                    "gain": None,
                    "perte": round(jours_abs * salaire_journalier_absence, 2),
                }
            )
        elif type_ev == "arret_maladie":
            # Symétrique de la branche `arret_maladie` du mode horaire
            # (`calcul_brut`) : sans elle, un jour d'arrêt était purement ignoré
            # en forfait jour — aucune retenue, brut = forfait plein — alors que
            # le maintien employeur, lui, était bien réinjecté par
            # `_appliquer_maintien_arret_maladie`. La retenue se valorise sur la
            # journée de forfait ; le maintien (et les IJSS subrogées) sont
            # ajoutés en aval par le moteur maintien, pas ici.
            jours_abs = _jours_evenement_absence(evenement)
            jours_absence_non_payes += jours_abs
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            montant_deduction = round(jours_abs * salaire_journalier_absence, 2)
            lignes_composants_brut.append(
                {
                    "libelle": f"Absence maladie du {date_absence}",
                    "quantite": jours_abs,
                    "taux": round(salaire_journalier_absence, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )

    # 3. Calcul des congés payés (somme des quotités : une demi-journée = 0,5)
    if jours_conges_dans_periode:
        nombre_jours_conges = sum(
            _jours_evenement_conges(ev) for ev in jours_conges_dans_periode
        )
        # Pour le forfait jour, on utilise le même calcul que pour les heures
        # mais adapté : on calcule le taux horaire équivalent pour la méthode du maintien
        # En pratique, pour le forfait jour, on utilise souvent la méthode du 1/10ème
        # ou le maintien de salaire

        # Calcul d'un taux horaire équivalent pour la compatibilité avec calcul_conges
        # On utilise une base de 7 heures par jour pour le calcul
        nombre_jours_conges * 7.0
        taux_horaire_equivalent = salaire_journalier / 7.0

        resultat_conges = calculer_indemnite_conges(
            contexte, nombre_jours_conges, taux_horaire_equivalent
        )

        dates_conges = _libelle_dates_conges(jours_conges_dans_periode)
        libelle_conges = "Absence congés payés " + (
            f"({_format_jours_conges(float(resultat_conges['nombre_jours']))} : {dates_conges})"
            if dates_conges
            else f"({_format_jours_conges(float(resultat_conges['nombre_jours']))})"
        )
        lignes_composants_brut.append(
            {
                "libelle": libelle_conges,
                "quantite": round(resultat_conges["total_heures_absence"], 2),
                "taux": None,
                "gain": None,
                "perte": resultat_conges["montant_retenue"],
            }
        )

        if resultat_conges["methode_retenue"] == "Maintien":
            lignes_composants_brut.append(
                {
                    "libelle": "Indemnité de congés payés (maintien de salaire)",
                    "quantite": round(resultat_conges["heures_base"], 2),
                    "taux": round(taux_horaire_equivalent, 4),
                    "gain": resultat_conges["indemnite_maintien_base"],
                    "perte": None,
                }
            )
            if resultat_conges["indemnite_maintien_hs"] > 0:
                lignes_composants_brut.append(
                    {
                        "libelle": "Indemnité de congés payés (partie HS)",
                        "quantite": round(resultat_conges["heures_hs"], 2),
                        "taux": round(taux_horaire_equivalent * 1.25, 4),
                        "gain": resultat_conges["indemnite_maintien_hs"],
                        "perte": None,
                    }
                )
        else:
            lignes_composants_brut.append(
                {
                    "libelle": "Indemnité de congés payés (règle du 1/10ème)",
                    "quantite": None,
                    "taux": None,
                    "gain": resultat_conges["montant_indemnite"],
                    "perte": None,
                }
            )

    # 3 bis. Mois entièrement absent : la retenue vaut exactement le salaire du
    # mois (hors prorata d'entrée/sortie), quel que soit le nombre de jours
    # ouvrés du mois. Sans ce complément, février (20 j ouvrés) laissait un
    # brut résiduel de 7,7 % à un salarié absent tout le mois (ANDRE MAJI
    # 02/2026 : 513,86 € au lieu de 0), tandis que mars (22 j) sur-déduisait.
    jours_ouvres_contrat = [
        jour for jour in jours_ouvres_mois if jour not in set(jours_hors_contrat)
    ]
    if jours_ouvres_contrat and jours_absence_non_payes >= len(jours_ouvres_contrat) - 1e-9:
        perte_entree_sortie = sum(
            (ligne.get("perte") or 0.0)
            for ligne in lignes_composants_brut
            if ligne.get("is_entree_sortie")
        )
        perte_absences = sum(
            (ligne.get("perte") or 0.0)
            for ligne in lignes_composants_brut
            if ligne.get("perte") and not ligne.get("is_entree_sortie")
        )
        complement = round(salaire_contractuel - perte_entree_sortie - perte_absences, 2)
        if abs(complement) >= 0.01:
            lignes_composants_brut.append(
                {
                    "libelle": "Absence sur tout le mois : retenue ramenée au salaire du mois",
                    "quantite": None,
                    "taux": None,
                    "gain": None if complement > 0 else round(-complement, 2),
                    "perte": complement if complement > 0 else None,
                }
            )

    # 4. Ajout des primes, avantages et calcul des totaux
    ligne_prime_anciennete = _calculer_prime_anciennete(
        contexte,
        calendrier_saisie=calendrier_saisie,
        date_debut_periode=date_debut_periode,
        date_fin_periode=date_fin_periode,
        jours_maintien=jours_maintien,
        actual_hours_raw=actual_hours_raw,
    )
    if ligne_prime_anciennete:
        lignes_composants_brut.append(ligne_prime_anciennete)

    if primes_saisies:
        for prime in primes_saisies:
            lignes_composants_brut.append(
                {
                    "libelle": prime.get("libelle", "Prime"),
                    "quantite": None,
                    "taux": None,
                    "gain": prime.get("montant", 0.0),
                    "perte": None,
                }
            )

    ligne_aen = _construire_ligne_avantages_en_nature(contexte)
    if ligne_aen:
        lignes_composants_brut.append(ligne_aen)
    for ligne_rappel in lignes_rappel_salaire(contexte):
        lignes_composants_brut.append(ligne_rappel)

    # Calcul du brut total
    total_gains = sum(
        ligne.get("gain", 0.0) or 0.0
        for ligne in lignes_composants_brut
        if not ligne.get("is_sous_total")
    )
    total_pertes = sum(
        ligne.get("perte", 0.0) or 0.0 for ligne in lignes_composants_brut
    )

    # Protection : Les déductions d'absence ne peuvent pas dépasser le salaire de base
    # (sauf si des primes/avantages sont ajoutés)
    salaire_base_seul = salaire_contractuel
    if total_pertes > salaire_base_seul:
        logger.warning(f"AVERTISSEMENT: Les déductions d'absence ({total_pertes:.2f} €) dépassent le salaire de base ({salaire_base_seul:.2f} €). Les déductions sont limitées au salaire de base.")
        # Limiter les déductions au salaire de base uniquement
        # (les primes et avantages peuvent compenser)
        total_pertes = min(total_pertes, salaire_base_seul)

    total_brut = total_gains - total_pertes

    # Protection finale : Le brut ne peut pas être négatif
    if total_brut < 0:
        logger.warning(f'AVERTISSEMENT: Le salaire brut calculé est négatif ({total_brut:.2f} €). Il est ramené à 0 €.')
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
        "nombre_jours_absence": round(nombre_jours_absence_injustifiee, 2),
    }
