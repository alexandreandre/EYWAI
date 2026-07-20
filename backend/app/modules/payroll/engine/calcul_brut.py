# moteur_paie/calcul_brut.py

from .contexte import ContextePaie
from . import legal_constants as lc
from datetime import date
from typing import Dict, Any, List, Optional
from .calcul_conges import calculer_indemnite_conges
from .salary_evolution_brut import (
    lignes_rappel_salaire,
    salaire_contractuel_avec_evolution,
)
from .salaire_contractuel import (
    heures_mensuelles_legales,
    heures_sup_structurelles_mensuelles as compute_hs_structurelles_mensuelles,
    salaire_contractuel_total_hors_hs_mode,
    salaire_hors_hs_structurelles,
    taux_horaire_base_hors_hs_structurelles,
)


def _heures_journalieres_contrat(duree_hebdo: float) -> float:
    """Durée journalière de référence (lun–ven) pour un jour d'absence isolé.

    Basée sur la durée légale (35 h) et non la durée contractuelle : une journée
    d'arrêt maladie/férié non payé se valorise sur la référence légale pour les
    salariés à temps plein (au-delà de 35 h, les heures sont structurelles et
    n'ont pas à être perdues sur une simple journée d'absence) ; en deçà (temps
    partiel), on garde le prorata contractuel.
    """
    if duree_hebdo and duree_hebdo > 0:
        return min(duree_hebdo, lc.DUREE_LEGALE_HEBDO) / 5.0
    return 7.0


def _heures_evenement_absence(evenement: Dict[str, Any], duree_hebdo: float) -> float:
    """Heures imputées sur une absence (impute la journée si heures absentes/nulles)."""
    heures = evenement.get("heures")
    if heures is None or heures == 0:
        return _heures_journalieres_contrat(duree_hebdo)
    return float(heures)


def _parse_date_contrat(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _facteur_prorata_entree_sortie(
    contexte: ContextePaie,
    date_debut_periode: date,
    date_fin_periode: date,
) -> float:
    """Prorata calendaire entrée / sortie en cours de mois (jours présents / jours du mois)."""
    contrat = contexte.contrat.get("contrat", {}) or {}
    date_entree = _parse_date_contrat(contrat.get("date_entree"))
    date_sortie = _parse_date_contrat(
        contrat.get("date_sortie") or contrat.get("date_fin_contrat")
    )

    debut_effectif = (
        max(date_debut_periode, date_entree) if date_entree else date_debut_periode
    )
    fin_effective = (
        min(date_fin_periode, date_sortie) if date_sortie else date_fin_periode
    )

    if fin_effective < debut_effectif:
        return 0.0

    jours_calendaires_mois = (date_fin_periode - date_debut_periode).days + 1
    jours_presence = (fin_effective - debut_effectif).days + 1
    if jours_calendaires_mois <= 0:
        return 1.0
    return jours_presence / jours_calendaires_mois


def _jour_ferie_est_paye(contexte: ContextePaie, evenement: Dict[str, Any]) -> bool:
    """Jour férié chômé payé, sauf condition d'ancienneté minimale (specificites_paie).

    Certaines CCN/usages subordonnent le maintien de salaire du jour férié chômé à une
    ancienneté minimale (ex. 3 mois) pour les salariés non mensualisés. Paramétré par
    l'entreprise via specificites_paie.jours_feries_anciennete_min_mois (absent = toujours payé).
    """
    spec = contexte.contrat.get("specificites_paie", {}) or {}
    seuil_mois = spec.get("jours_feries_anciennete_min_mois")
    if not seuil_mois:
        return True

    date_ferie = _parse_date_contrat(evenement.get("date_complete"))
    if not date_ferie:
        return True

    # 1er mai : chômé et payé sans condition d'ancienneté (art. L3133-4/5 C. trav.).
    if date_ferie.month == 5 and date_ferie.day == 1:
        return True

    # Journée de solidarité : jour férié travaillé/neutre par convention, sans effet
    # de paie ; date paramétrée par l'entreprise (parametres_paie.jour_solidarite).
    jour_solidarite = (contexte.entreprise.get("parametres_paie", {}) or {}).get(
        "jour_solidarite"
    )
    if jour_solidarite and _parse_date_contrat(jour_solidarite) == date_ferie:
        return True

    date_entree = _parse_date_contrat(
        contexte.contrat.get("contrat", {}).get("date_entree")
    )
    if not date_entree:
        return True

    mois_anciennete = (date_ferie.year - date_entree.year) * 12 + (
        date_ferie.month - date_entree.month
    )
    if date_ferie.day < date_entree.day:
        mois_anciennete -= 1
    return mois_anciennete >= float(seuil_mois)


def _calculer_prime_precarite_cdd(
    contexte: ContextePaie,
    salaire_brut_hors_precarite: float,
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any] | None:
    """Prime de précarité CDD (dernier mois), taux depuis payroll_config.cdd."""
    if not contexte.is_cdd or not contexte.est_dernier_mois_cdd(
        date_debut_periode, date_fin_periode
    ):
        return None

    spec = contexte.contrat.get("specificites_paie", {}) or {}
    if spec.get("exclure_prime_precarite") or spec.get("cdd_sans_precarite"):
        return None

    cfg = (contexte.baremes.get("cdd", {}) or {}).get("precarite", {}) or {}
    if cfg.get("actif") is False:
        return None
    taux = float(cfg.get("taux", 0.10))

    cumuls = (
        contexte.cumuls.get("cumuls", {})
        if isinstance(contexte.cumuls, dict)
        else {}
    )
    brut_cumule_contrat = float(cumuls.get("brut_total", 0.0)) + salaire_brut_hors_precarite
    montant = round(brut_cumule_contrat * taux, 2)
    if montant <= 0:
        return None

    return {
        "libelle": "Prime de précarité (CDD)",
        "quantite": None,
        "taux": taux,
        "gain": montant,
        "perte": None,
    }


def _calculer_ifm_interim(
    contexte: ContextePaie,
    salaire_brut_hors_indemnites: float,
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any] | None:
    """Indemnité de fin de mission (intérim), dernier mois de mission.

    Base légale : 10 % de la rémunération brute totale de la mission. Taux dans
    payroll_config.interim.ifm (défaut 0,10). Désactivable par flag
    specificites_paie.exclure_ifm.
    """
    if not contexte.is_interim or not contexte.est_dernier_mois_mission(
        date_debut_periode, date_fin_periode
    ):
        return None

    spec = contexte.contrat.get("specificites_paie", {}) or {}
    if spec.get("exclure_ifm"):
        return None

    cfg = (contexte.baremes.get("interim", {}) or {}).get("ifm", {}) or {}
    if cfg.get("actif") is False:
        return None
    taux = float(cfg.get("taux", 0.10))

    cumuls = (
        contexte.cumuls.get("cumuls", {})
        if isinstance(contexte.cumuls, dict)
        else {}
    )
    base = float(cumuls.get("brut_total", 0.0)) + salaire_brut_hors_indemnites
    montant = round(base * taux, 2)
    if montant <= 0:
        return None

    return {
        "libelle": "Indemnité de fin de mission (intérim)",
        "quantite": None,
        "taux": taux,
        "gain": montant,
        "perte": None,
    }


def _calculer_iccp_cdd(
    contexte: ContextePaie,
    salaire_brut_hors_precarite: float,
    montant_precarite: float,
    date_debut_periode: date,
    date_fin_periode: date,
) -> Dict[str, Any] | None:
    """Indemnité compensatrice de congés payés (dernier mois), méthode du 1/10e.

    Applicable au CDD et à la mission d'intérim. Base légale : 1/10 de la
    rémunération brute totale du contrat, prime de précarité / IFM comprise.
    Taux dans payroll_config.cdd.indemnite_conges (ou interim.indemnite_conges),
    défaut 0,10. Désactivable par flag specificites_paie.cdd_sans_iccp.
    """
    is_cdd_fin = contexte.is_cdd and contexte.est_dernier_mois_cdd(
        date_debut_periode, date_fin_periode
    )
    is_interim_fin = contexte.is_interim and contexte.est_dernier_mois_mission(
        date_debut_periode, date_fin_periode
    )
    if not (is_cdd_fin or is_interim_fin):
        return None

    if getattr(contexte, "exit_indemnities", None):
        return None

    if getattr(contexte, "block_iccp_cdd", False):
        return None

    spec = contexte.contrat.get("specificites_paie", {}) or {}
    if spec.get("cdd_sans_iccp") or spec.get("exclure_iccp"):
        return None

    cle_regime = "interim" if is_interim_fin else "cdd"
    cfg = (contexte.baremes.get(cle_regime, {}) or {}).get(
        "indemnite_conges", {}
    ) or {}
    if cfg.get("actif") is False:
        return None
    taux = float(cfg.get("taux", 0.10))

    cumuls = (
        contexte.cumuls.get("cumuls", {})
        if isinstance(contexte.cumuls, dict)
        else {}
    )
    base = (
        float(cumuls.get("brut_total", 0.0))
        + salaire_brut_hors_precarite
        + max(montant_precarite, 0.0)
    )
    montant = round(base * taux, 2)
    if montant <= 0:
        return None

    libelle_iccp = (
        "Indemnité compensatrice de congés payés (intérim)"
        if is_interim_fin
        else "Indemnité compensatrice de congés payés (CDD)"
    )
    return {
        "libelle": libelle_iccp,
        "quantite": None,
        "taux": taux,
        "gain": montant,
        "perte": None,
    }


def _taux_majoration_hs(contexte: ContextePaie, index: int = 0) -> Optional[float]:
    """Lit le taux de majoration HS depuis heures_supp (None si absent)."""
    if hasattr(contexte, "get_bareme_value"):
        val = contexte.get_bareme_value(
            "heures_supp",
            "regles_calcul_communes",
            "taux_majoration_par_defaut",
            "heures_supplementaires",
            index,
            "taux",
        )
    else:
        hs_list = (
            (getattr(contexte, "baremes", {}) or {})
            .get("heures_supp", {})
            .get("regles_calcul_communes", {})
            .get("taux_majoration_par_defaut", {})
            .get("heures_supplementaires", [])
        )
        val = None
        if isinstance(hs_list, list) and len(hs_list) > index:
            val = hs_list[index].get("taux")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _taux_majoration_hc(contexte: ContextePaie, index: int = 0) -> Optional[float]:
    """Lit le taux de majoration des heures complémentaires (temps partiel).

    Source : heures_supp.regles_calcul_communes.taux_majoration_par_defaut
    .heures_complementaires[index].taux (None si absent).
    """
    if hasattr(contexte, "get_bareme_value"):
        val = contexte.get_bareme_value(
            "heures_supp",
            "regles_calcul_communes",
            "taux_majoration_par_defaut",
            "heures_complementaires",
            index,
            "taux",
        )
    else:
        hc_list = (
            (getattr(contexte, "baremes", {}) or {})
            .get("heures_supp", {})
            .get("regles_calcul_communes", {})
            .get("taux_majoration_par_defaut", {})
            .get("heures_complementaires", [])
        )
        val = None
        if isinstance(hc_list, list) and len(hc_list) > index:
            val = hc_list[index].get("taux")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _get_salaire_horaire_base(
    contexte: ContextePaie, duree_hebdo_reelle: float
) -> float:
    salaire_mensuel = contexte.salaire_base_mensuel
    duree_legale_hebdo = lc.DUREE_LEGALE_HEBDO
    if (
        salaire_hors_hs_structurelles(contexte.contrat)
        and duree_hebdo_reelle > duree_legale_hebdo
    ):
        return taux_horaire_base_hors_hs_structurelles(salaire_mensuel)
    if duree_hebdo_reelle <= duree_legale_hebdo:
        heures_mensuelles = round((duree_hebdo_reelle * 52) / 12, 2)
        return salaire_mensuel / heures_mensuelles if heures_mensuelles > 0 else 0.0
    heures_mensuelles_legales = round((duree_legale_hebdo * 52) / 12, 2)
    heures_sup_structurelles_mensuelles = round(
        ((duree_hebdo_reelle - duree_legale_hebdo) * 52) / 12, 2
    )
    majoration_hs = _taux_majoration_hs(contexte, 0)
    if majoration_hs is None:
        majoration_hs = 0.0
    heures_equivalentes_majorees = heures_mensuelles_legales + (
        heures_sup_structurelles_mensuelles * (1 + majoration_hs)
    )
    return (
        salaire_mensuel / heures_equivalentes_majorees
        if heures_equivalentes_majorees > 0
        else 0.0
    )


def _construire_ligne_avantages_en_nature(
    contexte: ContextePaie,
) -> Dict[str, Any] | None:
    # Cette fonction reste inchangée
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


# def _calculer_hs_semaine(heures_travaillees: float, duree_contrat_hebdo: float, regles_majoration: List[Dict]) -> Dict[float, float]:
#     """
#     Calcule la répartition des heures supplémentaires pour UNE semaine.
#     """
#     heures_sup_semaine = max(0, heures_travaillees - duree_contrat_hebdo)
#     if heures_sup_semaine == 0:
#         return {}

#     hs_par_taux = {}
#     heures_restantes_a_ventiler = heures_sup_semaine

#     # On prend en compte les HS structurelles déjà incluses dans la durée du contrat
#     heures_structurelles = max(0, duree_contrat_hebdo - 35)

#     # Le seuil de passage à 50% est après 8h au total (structurelles + conjoncturelles)
#     seuil_majoration_max = 8.0

#     # On calcule combien d'heures à 25% on peut encore faire cette semaine
#     heures_a_25_restantes = max(0, seuil_majoration_max - heures_structurelles)

#     taux_25 = regles_majoration[0].get('taux', 0.25)
#     taux_50 = regles_majoration[1].get('taux', 0.50)

#     # On ventile les heures sup de la semaine
#     heures_a_25 = min(heures_restantes_a_ventiler, heures_a_25_restantes)
#     if heures_a_25 > 0:
#         hs_par_taux[taux_25] = heures_a_25
#         heures_restantes_a_ventiler -= heures_a_25

#     if heures_restantes_a_ventiler > 0:
#         hs_par_taux[taux_50] = heures_restantes_a_ventiler

#     return hs_par_taux

# Fichier : moteur_paie/calcul_brut.py

# moteur_paie/calcul_brut.py


def calculer_salaire_brut(
    contexte: ContextePaie,
    calendrier_saisie: List[Dict[str, Any]],
    date_debut_periode: date,
    date_fin_periode: date,
    primes_saisies: List[Dict[str, Any]] = None,
    jours_maintien: Optional[set[int]] = None,
    actual_hours_raw: Optional[List[Dict[str, Any]]] = None,
    actual_hours_all_months: Optional[List[Dict[str, Any]]] = None,
    nb_jours_travail_planifies: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calcule le salaire brut à partir d'une liste d'événements de paie déjà analysés.

    ``nb_jours_travail_planifies`` (optionnel) : nombre de jours de type
    ``"travail"`` OU ``"conges_payes"`` dans le `planned_calendar` BRUT du mois
    (avant analyse) — les congés payés comptent aussi comme "couvert" (le
    salarié est normalement rémunéré via l'indemnité de CP, ce n'est PAS une
    absence intégrale non rémunérée). Sert UNIQUEMENT à détecter une absence
    couvrant l'intégralité du mois calendaire (aucun jour de travail NI de CP
    planifié nulle part), afin de compléter la retenue jusqu'au montant
    mensualisé total (fériés/repos inclus, cf. Cegid MBC mai 2026 SAFI2/BABA).
    ⚠️ Ne PAS utiliser les accumulateurs d'heures travaillées
    du présent calcul pour cette détection : `heures_travail_base_total` est
    TOUJOURS à 0 pour un salarié "heures" (le type d'événement "travail_base"
    n'est émis que par le chemin forfait-jour, jamais par
    `analyser_horaires_du_mois`) — l'utiliser comme signal a provoqué une
    régression sur FUCKAR (Colorplast, mois normal sans pointage soumis) lors
    d'une première tentative. Le signal fiable est le calendrier BRUT, pas les
    événements analysés. Si `None` (valeur par défaut, tous les appelants
    existants sauf `payslip_run_heures.py`), le complément ne se déclenche
    jamais — comportement strictement inchangé.
    """
    lignes_composants_brut = []
    duree_legale_hebdo = lc.DUREE_LEGALE_HEBDO
    duree_contrat_hebdo = contexte.duree_hebdo_contrat
    salaire_contractuel = salaire_contractuel_avec_evolution(
        contexte, contexte.salaire_base_mensuel
    )
    facteur_prorata = _facteur_prorata_entree_sortie(
        contexte, date_debut_periode, date_fin_periode
    )
    if facteur_prorata < 1.0:
        salaire_contractuel = round(salaire_contractuel * facteur_prorata, 2)
    taux_horaire_de_base = _get_salaire_horaire_base(contexte, duree_contrat_hebdo)

    majoration_hs25 = _taux_majoration_hs(contexte, 0)
    majoration_hs50 = _taux_majoration_hs(contexte, 1)
    if majoration_hs25 is None:
        majoration_hs25 = 0.0
    if majoration_hs50 is None:
        majoration_hs50 = 0.0

    remuneration_hs_structurelles = 0.0
    heures_sup_structurelles_mensuelles = 0.0

    # 1. Décomposition du salaire de base
    if duree_contrat_hebdo < duree_legale_hebdo:
        heures_mensuelles_contrat = round((duree_contrat_hebdo * 52) / 12, 2)
        gain_base = round(salaire_contractuel, 2)
        if facteur_prorata < 1.0:
            taux_affichage = (
                gain_base / heures_mensuelles_contrat if heures_mensuelles_contrat else 0
            )
        else:
            taux_affichage = round(taux_horaire_de_base, 4)
        lignes_composants_brut.append(
            {
                "libelle": "Salaire de base",
                "quantite": heures_mensuelles_contrat,
                "taux": round(taux_affichage, 4),
                "gain": gain_base,
                "perte": None,
            }
        )
        remuneration_hs_structurelles = 0.0
        heures_sup_structurelles_mensuelles = 0.0
    else:
        heures_mensuelles_legales_val = heures_mensuelles_legales()
        hors_hs = salaire_hors_hs_structurelles(contexte.contrat)
        if facteur_prorata < 1.0:
            salaire_base_35h = round(salaire_contractuel, 2)
        elif hors_hs:
            salaire_base_35h = round(salaire_contractuel, 2)
        else:
            salaire_base_35h = heures_mensuelles_legales_val * taux_horaire_de_base
        lignes_composants_brut.append(
            {
                "libelle": "Salaire de base",
                "quantite": heures_mensuelles_legales_val,
                "taux": round(
                    salaire_base_35h / heures_mensuelles_legales_val
                    if heures_mensuelles_legales_val
                    else taux_horaire_de_base,
                    4,
                ),
                "gain": round(salaire_base_35h, 2),
                "perte": None,
            }
        )
        remuneration_hs_structurelles = 0.0
        heures_sup_structurelles_mensuelles = 0.0
        if duree_contrat_hebdo > duree_legale_hebdo:
            heures_sup_structurelles_mensuelles = compute_hs_structurelles_mensuelles(
                duree_contrat_hebdo
            )
            if hors_hs:
                taux_horaire_majore = taux_horaire_de_base * (1 + majoration_hs25)
                remuneration_hs_structurelles = round(
                    heures_sup_structurelles_mensuelles * taux_horaire_majore, 2
                )
                total_contractuel = round(
                    salaire_base_35h + remuneration_hs_structurelles, 2
                )
            else:
                remuneration_hs_structurelles = salaire_contractuel - salaire_base_35h
                total_contractuel = salaire_contractuel
            taux_horaire_majore = (
                remuneration_hs_structurelles / heures_sup_structurelles_mensuelles
                if heures_sup_structurelles_mensuelles > 0
                else 0
            )
            majoration_pct = (
                (taux_horaire_majore / taux_horaire_de_base - 1) * 100
                if taux_horaire_de_base > 0
                else 0
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Heures suppl. structurelles majorées à {majoration_pct:.0f}%",
                    "quantite": heures_sup_structurelles_mensuelles,
                    "taux": round(taux_horaire_majore, 4),
                    "gain": round(remuneration_hs_structurelles, 2),
                    "perte": None,
                }
            )
            lignes_composants_brut.append(
                {
                    "libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL",
                    "quantite": round(
                        heures_mensuelles_legales_val + heures_sup_structurelles_mensuelles,
                        2,
                    ),
                    "taux": None,
                    "gain": total_contractuel,
                    "perte": None,
                    "is_sous_total": True,
                }
            )

    # Montant mensualisé total du salaire de base (+ HS structurelles si contrat
    # au-dessus de la durée légale) — référence pour la retenue "mois complet
    # d'absence" ci-dessous (indépendant du branchement temps plein/temps
    # partiel/HS structurelles).
    montant_base_mensualise = (
        gain_base
        if duree_contrat_hebdo < duree_legale_hebdo
        else round(salaire_base_35h + remuneration_hs_structurelles, 2)
    )

    # 2. Préparation des taux et des accumulateurs
    taux_hs25 = taux_horaire_de_base * (1 + majoration_hs25)
    taux_hs50 = taux_horaire_de_base * (1 + majoration_hs50)

    # Heures complémentaires (temps partiel) : majorations dédiées (10 % puis 25 %).
    majoration_hc1 = _taux_majoration_hc(contexte, 0)
    majoration_hc2 = _taux_majoration_hc(contexte, 1)
    if majoration_hc1 is None:
        majoration_hc1 = 0.10
    if majoration_hc2 is None:
        majoration_hc2 = 0.25
    taux_hc1 = taux_horaire_de_base * (1 + majoration_hc1)
    taux_hc2 = taux_horaire_de_base * (1 + majoration_hc2)

    smoothing_gain = float(getattr(contexte, "modulation_smoothing_gain", 0) or 0)
    if smoothing_gain > 0:
        lignes_composants_brut.append(
            {
                "libelle": "Lissage modulation",
                "quantite": None,
                "taux": None,
                "gain": round(smoothing_gain, 2),
                "perte": None,
            }
        )

    heures_travail_base_total = 0.0
    heures_travail_hs25_total = 0.0
    heures_travail_hs50_total = 0.0
    heures_travail_hc1_total = 0.0
    heures_travail_hc2_total = 0.0
    heures_absence_hs_total = 0.0  #

    jours_dans_periode = [
        j
        for j in calendrier_saisie
        if "date_complete" in j
        and (
            date_debut_periode
            <= date.fromisoformat(j["date_complete"])
            <= date_fin_periode
            # Régularisation antérieure (cf. payslip_run_common
            # .regularisation_events_from_calendar) : sa date d'origine est
            # volontairement antérieure au mois de paie courant, mais son
            # effet doit bien être appliqué sur CE bulletin.
            or j.get("is_regularisation_anterieure")
        )
    ]

    # 3. Traitement de tous les événements de la période
    jours_conges_dans_periode = []
    deduction_arret_maladie_total = 0.0
    jours_absence_legale_equivalents = 0.0
    # Cumul des retenues "absence non rémunérée" / "arrêt maladie" / "réduction
    # HS structurelles" déjà appliquées jour par jour — comparé au montant
    # mensualisé total (ci-dessus) UNIQUEMENT si `nb_jours_travail_planifies==0`
    # (aucun jour "travail" dans le calendrier BRUT du mois, cf. docstring).
    montant_absence_pleine_total = 0.0
    for evenement in jours_dans_periode:
        type_ev = evenement.get("type", "")
        heures = evenement.get("heures", 0.0)

        if type_ev == "travail_base" or type_ev == "absence_justifiee":
            heures_travail_base_total += heures
        elif type_ev == "travail_hs25":
            heures_travail_hs25_total += heures
        elif type_ev == "travail_hs50":
            heures_travail_hs50_total += heures
        elif type_ev in ("travail_hc", "travail_hc10"):
            heures_travail_hc1_total += heures
        elif type_ev == "travail_hc25":
            heures_travail_hc2_total += heures
        elif "absence_injustifiee" in type_ev:
            if actual_hours_all_months is not None:
                date_abs = date.fromisoformat(evenement["date_complete"])
                from app.modules.payroll.planning_repli import mois_sans_pointage

                if mois_sans_pointage(
                    actual_hours_all_months,
                    annee=date_abs.year,
                    mois=date_abs.month,
                ):
                    continue

            taux_deduction = taux_horaire_de_base
            is_hs_absence = False
            if "hs25" in type_ev:
                taux_deduction = taux_hs25
                is_hs_absence = True

            heures_abs = _heures_evenement_absence(evenement, duree_contrat_hebdo)
            if is_hs_absence:
                heures_absence_hs_total += heures_abs

            montant_deduction = round(heures_abs * taux_deduction, 2)
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            libelle_absence = (
                f"Absence injustifiée du {date_absence} ({type_ev.split('_')[-1]})"
            )
            lignes_composants_brut.append(
                {
                    "libelle": libelle_absence,
                    "quantite": heures_abs,
                    "taux": round(taux_deduction, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )

        elif type_ev == "absence_non_remuneree":
            heures_abs = _heures_evenement_absence(evenement, duree_contrat_hebdo)
            montant_deduction = round(heures_abs * taux_horaire_de_base, 2)
            # Une régularisation antérieure (cf. `is_regularisation_anterieure`)
            # ne doit PAS contribuer à la quote-part des HS structurelles
            # mensualisées DU MOIS COURANT (cette quote-part concerne le mois
            # d'origine, déjà clos — Cegid ne réduit pas les HS structurelles
            # de mai pour une absence d'avril rattachée au bulletin de mai,
            # cf. KIRMIZI mai 2026 MBC : sans cette exclusion, la retenue est
            # sur-évaluée d'une réduction HS structurelles fantôme).
            if not evenement.get("is_regularisation_anterieure"):
                jours_absence_legale_equivalents += (
                    heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                )
                montant_absence_pleine_total += montant_deduction
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Absence non rémunérée du {date_absence}",
                    "quantite": heures_abs,
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )
        elif type_ev == "conges_payes":
            jours_conges_dans_periode.append(evenement)
        elif type_ev == "ferie" and not _jour_ferie_est_paye(contexte, evenement):
            heures_abs = _heures_evenement_absence(evenement, duree_contrat_hebdo)
            montant_deduction = round(heures_abs * taux_horaire_de_base, 2)
            if not evenement.get("is_regularisation_anterieure"):
                jours_absence_legale_equivalents += (
                    heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                )
            date_absence = date.fromisoformat(evenement["date_complete"]).strftime(
                "%d/%m/%y"
            )
            lignes_composants_brut.append(
                {
                    "libelle": f"Abs. jour férié non payé du {date_absence}",
                    "quantite": heures_abs,
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": None,
                    "perte": montant_deduction,
                }
            )
        elif type_ev == "arret_maladie":
            # La retenue d'un jour d'arrêt maladie se valorise sur la référence
            # journalière LÉGALE (7 h temps plein), jamais sur les heures
            # planifiées du jour (souvent 7,5 h contractuelles issues d'un
            # template) : le salaire de base est mensualisé sur 151,67 h légales
            # et la quote-part d'HS structurelle est déjà retirée séparément par
            # la ligne « Réduction HS structurelles ». Déduire 7,5 h au taux de
            # base retirerait deux fois la part structurelle (sur-déduction, cf.
            # OSMANI2 MBC mai 2026 : 7,5 h vs 7 h → −0,5 h/jour de trop). Le
            # `min` préserve les arrêts fractionnaires (demi-journée < réf.
            # légale, ex. 3,5 h), imputés à leur valeur réelle.
            heures_abs = min(
                _heures_evenement_absence(evenement, duree_contrat_hebdo),
                _heures_journalieres_contrat(duree_contrat_hebdo),
            )
            montant_deduction = round(heures_abs * taux_horaire_de_base, 2)
            deduction_arret_maladie_total += montant_deduction
            if not evenement.get("is_regularisation_anterieure"):
                jours_absence_legale_equivalents += (
                    heures_abs / lc.DUREE_LEGALE_HEBDO * 5
                )
                montant_absence_pleine_total += montant_deduction
            lignes_composants_brut.append(
                {
                    "libelle": "Absence arrêt maladie (jours déduction)",
                    "quantite": heures_abs,
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": None,
                    "perte": montant_deduction,
                    "is_arret_maladie": True,
                }
            )

    # Réduction proportionnelle des HS structurelles mensualisées (salaire_hors_hs_structurelles)
    # pour les journées d'absence déduites sur la référence légale : le salarié absent un
    # jour ne génère pas non plus sa quote-part de l'heure supplémentaire structurelle de
    # ce jour-là (17,33 h/mois répartis sur les jours ouvrés légaux du mois).
    if jours_absence_legale_equivalents > 0 and heures_sup_structurelles_mensuelles > 0:
        jours_legaux_mensuels = heures_mensuelles_legales() / (
            lc.DUREE_LEGALE_HEBDO / 5
        )
        heures_hs_perdues = round(
            heures_sup_structurelles_mensuelles
            * jours_absence_legale_equivalents
            / jours_legaux_mensuels,
            2,
        )
        if heures_hs_perdues > 0:
            montant_reduction_hs = round(heures_hs_perdues * taux_horaire_majore, 2)
            montant_absence_pleine_total += montant_reduction_hs
            lignes_composants_brut.append(
                {
                    "libelle": "Réduction HS structurelles (jours d'absence)",
                    "quantite": heures_hs_perdues,
                    "taux": round(taux_horaire_majore, 4),
                    "gain": None,
                    "perte": montant_reduction_hs,
                    "is_reduction_hs": True,
                }
            )

    # Absence couvrant l'INTÉGRALITÉ du mois calendaire (cf. Cegid MBC mai 2026
    # SAFI2/BABA — arrêt maladie/prolongation de rechute, AUCUN jour "travail"
    # planifié nulle part dans le calendrier BRUT du mois, pas seulement "zéro
    # heure travaillée" au sens des accumulateurs ci-dessus qui sont TOUJOURS à
    # 0 pour un salarié "heures", cf. docstring). La retenue jour-ouvré-par-
    # jour-ouvré ne déduit pas les jours fériés/repos compris dans la période
    # (ils ne sont ni travaillés ni "absents" au sens du calendrier), mais
    # Cegid déduit alors l'intégralité du salaire mensualisé. Gaté strictement
    # sur `nb_jours_travail_planifies == 0` (calendrier brut fourni par
    # l'appelant, cf. payslip_run_heures.py) : ne peut PAS se déclencher pour
    # un salarié qui a ne serait-ce qu'un seul jour "travail" planifié dans le
    # mois, quel que soit l'état du pointage.
    if (
        nb_jours_travail_planifies == 0
        and montant_absence_pleine_total > 0
    ):
        complement_absence_pleine = round(
            montant_base_mensualise - montant_absence_pleine_total, 2
        )
        if complement_absence_pleine > 0.01:
            lignes_composants_brut.append(
                {
                    "libelle": "Complément retenue absence intégrale du mois "
                    "(jours fériés/repos inclus)",
                    "quantite": None,
                    "taux": None,
                    "gain": None,
                    "perte": complement_absence_pleine,
                }
            )

    # Saisie manuelle (monthly_inputs) : HS conjoncturelles déclarées sans badgeage.
    declared_conj = float(contexte.heures_sup_du_mois or 0)
    declared_conj_50 = float(contexte.heures_sup_du_mois_50 or 0)
    if declared_conj > 0 or declared_conj_50 > 0:
        calendar_conj = heures_travail_hs25_total + heures_travail_hs50_total
        if abs((declared_conj + declared_conj_50) - calendar_conj) > 0.001:
            heures_travail_hs25_total = round(declared_conj, 2)
            heures_travail_hs50_total = round(declared_conj_50, 2)

    # 4. Ajout des lignes de GAIN pour les heures travaillées (après accumulation)
    # if heures_travail_base_total > 0:
    #     lignes_composants_brut.append({"libelle": "Heures normales travaillées", "quantite": round(heures_travail_base_total, 2), "taux": round(taux_horaire_de_base, 4), "gain": round(heures_travail_base_total * taux_horaire_de_base, 2), "perte": None})
    if heures_travail_hs25_total > 0:
        gain = round(heures_travail_hs25_total * taux_hs25, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures suppl. majorées à {majoration_hs25 * 100:.0f}%",
                "quantite": round(heures_travail_hs25_total, 2),
                "taux": round(taux_hs25, 4),
                "gain": gain,
                "perte": None,
            }
        )
    if heures_travail_hs50_total > 0:
        gain = round(heures_travail_hs50_total * taux_hs50, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures suppl. majorées à {majoration_hs50 * 100:.0f}%",
                "quantite": round(heures_travail_hs50_total, 2),
                "taux": round(taux_hs50, 4),
                "gain": gain,
                "perte": None,
            }
        )
    # Heures complémentaires (temps partiel) : rémunération ordinaire majorée,
    # sans régime social des heures supplémentaires.
    if heures_travail_hc1_total > 0:
        gain = round(heures_travail_hc1_total * taux_hc1, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures complémentaires majorées à {majoration_hc1 * 100:.0f}%",
                "quantite": round(heures_travail_hc1_total, 2),
                "taux": round(taux_hc1, 4),
                "gain": gain,
                "perte": None,
            }
        )
    if heures_travail_hc2_total > 0:
        gain = round(heures_travail_hc2_total * taux_hc2, 2)
        lignes_composants_brut.append(
            {
                "libelle": f"Heures complémentaires majorées à {majoration_hc2 * 100:.0f}%",
                "quantite": round(heures_travail_hc2_total, 2),
                "taux": round(taux_hc2, 4),
                "gain": gain,
                "perte": None,
            }
        )

    # 5. Calcul final des congés
    if jours_conges_dans_periode:
        resultat_conges = calculer_indemnite_conges(
            contexte, len(jours_conges_dans_periode), taux_horaire_de_base
        )
        lignes_composants_brut.append(
            {
                "libelle": f"Absence congés payés ({resultat_conges['nombre_jours']} jours)",
                "quantite": round(resultat_conges["total_heures_absence"], 2),
                "taux": None,
                "gain": None,
                "perte": resultat_conges["montant_retenue"],
            }
        )
        if resultat_conges["methode_retenue"] == "Maintien":
            lignes_composants_brut.append(
                {
                    "libelle": "Indemnité de congés payés (partie base)",
                    "quantite": round(resultat_conges["heures_base"], 2),
                    "taux": round(taux_horaire_de_base, 4),
                    "gain": resultat_conges["indemnite_maintien_base"],
                    "perte": None,
                }
            )
            if resultat_conges["indemnite_maintien_hs"] > 0:
                salaire_horaire_majore = taux_horaire_de_base * (1 + majoration_hs25)
                lignes_composants_brut.append(
                    {
                        "libelle": f"Indemnité de congés payés (partie HS {majoration_hs25 * 100:.0f}%)",
                        "quantite": round(resultat_conges["heures_hs"], 2),
                        "taux": round(salaire_horaire_majore, 4),
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

    # 6. Ajout des primes, avantages et calcul des totaux
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

    # Prime de précarité CDD (dernier mois) — calculée avant le total brut.
    total_gains_inter = sum(
        ligne.get("gain", 0.0) or 0.0
        for ligne in lignes_composants_brut
        if not ligne.get("is_sous_total")
    )
    total_pertes_inter = sum(
        ligne.get("perte", 0.0) or 0.0 for ligne in lignes_composants_brut
    )
    brut_hors_precarite = total_gains_inter - total_pertes_inter
    ligne_precarite = _calculer_prime_precarite_cdd(
        contexte, brut_hors_precarite, date_debut_periode, date_fin_periode
    )
    montant_indemnite_fin = 0.0
    if ligne_precarite:
        lignes_composants_brut.append(ligne_precarite)
        montant_indemnite_fin = ligne_precarite.get("gain", 0.0) or 0.0

    # Indemnité de fin de mission (intérim), dernier mois — équivalent précarité.
    ligne_ifm = _calculer_ifm_interim(
        contexte, brut_hors_precarite, date_debut_periode, date_fin_periode
    )
    if ligne_ifm:
        lignes_composants_brut.append(ligne_ifm)
        montant_indemnite_fin = ligne_ifm.get("gain", 0.0) or 0.0

    # Indemnité compensatrice de congés payés (1/10e), dernier mois CDD/mission.
    ligne_iccp = _calculer_iccp_cdd(
        contexte,
        brut_hors_precarite,
        montant_indemnite_fin,
        date_debut_periode,
        date_fin_periode,
    )
    if ligne_iccp:
        lignes_composants_brut.append(ligne_iccp)

    # Le calcul du brut total reste inchangé
    total_gains = sum(
        ligne.get("gain", 0.0) or 0.0
        for ligne in lignes_composants_brut
        if not ligne.get("is_sous_total")
    )
    total_pertes = sum(
        ligne.get("perte", 0.0) or 0.0 for ligne in lignes_composants_brut
    )
    total_brut = total_gains - total_pertes

    # Étape 1 : Isoler les gains liés aux HS (structurelles et conjoncturelles)
    # Note: La rémunération des HS structurelles est déjà calculée plus haut.
    remuneration_hs_conjoncturelles = sum(
        ligne.get("gain", 0.0)
        for ligne in lignes_composants_brut
        if ligne.get("libelle", "").startswith("Heures suppl. majorées")
    )

    # Étape 2 (NOUVEAU) : Isoler les pertes liées aux HS
    pertes_heures_supp = sum(
        ligne.get("perte", 0.0)
        for ligne in lignes_composants_brut
        if ligne.get("is_reduction_hs")
        or (
            "absence" in ligne.get("libelle", "").lower()
            and (
                "hs25" in ligne.get("libelle", "").lower()
                or "hs50" in ligne.get("libelle", "").lower()
            )
        )
    )

    # Étape 3 : Calculer la rémunération NETTE des heures supplémentaires
    remuneration_hs_totale = (
        remuneration_hs_structurelles + remuneration_hs_conjoncturelles
    ) - pertes_heures_supp

    # Le total des heures supp pour la déduction forfaitaire patronale n'est pas impacté par les absences
    heures_sup_conjoncturelles = heures_travail_hs25_total + heures_travail_hs50_total
    total_heures_supp_mois = (
        heures_sup_structurelles_mensuelles + heures_sup_conjoncturelles
    ) - heures_absence_hs_total

    # --- FIN DU BLOC CORRIGÉ ---

    # Heures complémentaires du mois : exposées au calcul des cotisations pour
    # relever le prorata du plafond SS temps partiel (assiette).
    try:
        contexte.heures_complementaires_mois = round(
            heures_travail_hc1_total + heures_travail_hc2_total, 2
        )
    except Exception:
        pass

    return {
        "salaire_brut_total": round(total_brut, 2),
        "lignes_composants_brut": lignes_composants_brut,
        "remuneration_brute_heures_supp": round(remuneration_hs_totale, 2),
        "total_heures_supp": round(total_heures_supp_mois, 2),
        # HS conjoncturelles seules (au-delà de l'horaire contractuel) : utile
        # pour le SMIC de référence de la réduction (heures rémunérées = contrat
        # + conjoncturelles + complémentaires), sans double-compter le structurel.
        "heures_sup_conjoncturelles": round(heures_sup_conjoncturelles, 2),
        "deduction_arret_maladie": round(deduction_arret_maladie_total, 2),
        "heures_complementaires": round(
            heures_travail_hc1_total + heures_travail_hc2_total, 2
        ),
    }
