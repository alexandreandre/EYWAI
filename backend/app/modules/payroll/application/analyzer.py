"""
Analyse des horaires et production des événements de paie.

Source de vérité unique pour analyser_horaires_du_mois (signature in-memory).
Migré depuis services/payroll_analyzer.py (fusion avec backend_api/payroll_analyzer.py).
"""
from app.core.logging import get_logger, log_payroll_debug

from app.modules.payroll.planning_repli import mois_sans_pointage

from datetime import date
from typing import Any, Dict, List
from collections import defaultdict

# Champs à recoller sur les événements agrégés (jour, type, heures) pour le maintien de salaire
# et la cohérence avec payslip_run_heures._extraire_arret_pour_maintien / calcul_brut.

logger = get_logger("modules.payroll.application.analyzer")

# Types dont l'effet paie dépend d'un repli à durée nulle (ex. déduction arrêt
# maladie / jour férié non payé calculée sur la durée contractuelle du jour quand
# heures_prevues=0) : ne jamais les filtrer même à 0 h, sinon l'événement n'atteint
# jamais calcul_brut et l'absence n'est jamais déduite. Partagé avec l'analyseur
# forfait-jour (`engine.analyser_jours_forfait`), qui a le même repli.
# NOTE : `conges_payes` n'y figure pas car la récupération modulation est
# projetée sous le MÊME type calendrier (absence_calendar) ; la distinction se
# fait par le marqueur `source_absence` posé à la génération depuis la demande
# validée d'origine (payslip_generator._stamp_source_absence_conges) — seuls
# les vrais congés payés sont conservés à 0 h (cf. _conserver_evenement_a_
# zero_heure). Un jour sans marqueur (planning pur, reprise DSN) reste ignoré.
TYPES_SIGNIFICATIFS_A_ZERO_HEURE: frozenset[str] = frozenset({"arret_maladie", "ferie"})

_MAINTIEN_EVENT_META_KEYS: tuple[str, ...] = (
    "arret_type",
    "subrogation_active",
    "nombre_enfants",
    "is_temps_partiel",
    "quotite_temps_partiel",
    "historique_arrets_annee",
    "date_dernier_arret",
    "salaire_periode_reelle",
    "maintien_base_ouvree",
    "date_debut_arret_reel",  # vrai début d'un arrêt multi-mois (épuisement maintien)
    "date_fin_arret_reel",  # vraie fin calendaire (week-end/férié en bord de mois)
    "quotite_absence",  # fraction de jour d'absence (0.5 = demi-journée de CP)
    "demi_journee",  # "matin" / "apres_midi" — informatif (affichage/traçabilité)
    "source_absence",  # type de la demande d'origine (conge_paye / recuperation_modulation)
)


def _metadata_for_aggregated_event(
    evenements_finaux: List[Dict[str, Any]],
    mois: int,
    jour: int,
    type_ev: str,
) -> Dict[str, Any]:
    """Reprend les métadonnées perdues lors de l'agrégation (ex. arret_type sur arret_maladie)."""
    meta: Dict[str, Any] = {}
    for ev in evenements_finaux:
        if ev.get("mois", mois) != mois:
            continue
        if ev.get("jour") != jour or ev.get("type") != type_ev:
            continue
        for k in _MAINTIEN_EVENT_META_KEYS:
            if k in ev and k not in meta:
                meta[k] = ev[k]
        if meta.get("arret_type"):
            break
    return meta


def _conserver_evenement_a_zero_heure(type_ev: str, meta: Dict[str, Any]) -> bool:
    """True si un événement à 0 h doit tout de même atteindre le bulletin.

    `arret_maladie` / `ferie` : retenue (repli durée contractuelle).
    Bornes `date_*_arret_reel` : week-end/repos d'un arrêt non retypé, pour
    que le décompte calendaire (prévoyance / IJSS) survive à un mois qui
    ne contient que ce débordement — sans retenue 7 h (`type` inchangé).
    `quotite_absence` < 1 : demi-journée de CP (projetée à 0 h) — calcul_brut
    la compte en jours (0,5), l'événement doit donc survivre. Volontairement
    limité aux demi-journées : cf. NOTE sur TYPES_SIGNIFICATIFS_A_ZERO_HEURE.
    """
    if type_ev in TYPES_SIGNIFICATIFS_A_ZERO_HEURE:
        return True
    if type_ev == "conges_payes" and meta.get("source_absence") == "conge_paye":
        # Un VRAI congé payé validé (marqueur posé à la génération depuis la
        # demande d'origine) atteint le bulletin même à 0 h : retenue +
        # indemnité + arbitrage 1/10e. La récupération modulation, projetée
        # sous le MÊME type calendrier, reste ignorée (aucune ligne CP) ; un
        # jour sans marqueur (planning pur, reprise DSN) garde le comportement
        # historique.
        return True
    try:
        quotite = float(meta.get("quotite_absence") or 0.0)
    except (TypeError, ValueError):
        quotite = 0.0
    if 0.0 < quotite < 1.0:
        return True
    return bool(meta.get("date_debut_arret_reel") or meta.get("date_fin_arret_reel"))


def _absences_injustifiees_de_la_semaine(
    data: Dict[str, Any],
    reel_data: List[Dict[str, Any]],
    annee: int,
    duree_hebdo_semaine: float,
) -> List[Dict[str, Any]]:
    """Événements d'absence injustifiée d'une semaine, après bilan.

    Le bilan porte sur les jours de travail prévus qui ont un pointage :
    manque (prévu − fait) ou surplus (fait − prévu) de chaque jour. Le surplus
    de la semaine compense les manques dans l'ordre des jours ; ce qui reste
    est retenu sur les derniers jours manqués. Une semaine dont le total est
    atteint ne porte donc aucune absence, même si un jour est incomplet.

    Restent neutres : un mois sans pointage (repli planning), un jour prévu
    sans pointage (un trou n'est pas une absence), un jour non prévu (ses
    heures comptent pour les heures sup, pas ici).

    Le typage base / hs25 par position dans la semaine est conservé : il n'a
    plus d'effet sur un contrat de plus de 35 h (répartition 35/39 dans
    calcul_brut), mais reste lu pour un contrat à 35 h.
    """
    duree_contrat_centiemes = int(duree_hebdo_semaine * 100)
    jours_prevus = sorted(data["prevu"], key=lambda x: (x["mois"], x["jour"]))

    # 1. Manque et surplus de chaque jour prévu pointé (centièmes d'heure).
    heures_faites: Dict[tuple, int] = {}
    manques: Dict[tuple, int] = {}
    surplus_semaine = 0
    for jour_prevu in jours_prevus:
        cle = (jour_prevu["mois"], jour_prevu["jour"])
        heures_prevues_jour = int((jour_prevu.get("heures_prevues") or 0.0) * 100)
        jour_annee = jour_prevu.get("annee", annee)
        if mois_sans_pointage(reel_data, annee=jour_annee, mois=jour_prevu["mois"]):
            heures_faites[cle] = heures_prevues_jour
            continue
        jour_reel = next(
            (
                j
                for j in data["reel"]
                if j["jour"] == jour_prevu["jour"] and j["mois"] == jour_prevu["mois"]
            ),
            None,
        )
        if jour_reel is None:
            heures_faites[cle] = heures_prevues_jour
            continue
        heures_faites_jour = int((jour_reel.get("heures_faites") or 0.0) * 100)
        heures_faites[cle] = heures_faites_jour
        ecart = heures_faites_jour - heures_prevues_jour
        if ecart < 0:
            manques[cle] = -ecart
        elif ecart > 0:
            surplus_semaine += ecart

    # 2. Le surplus compense les premiers jours manqués.
    for cle in list(manques):
        compensation = min(surplus_semaine, manques[cle])
        manques[cle] -= compensation
        surplus_semaine -= compensation

    # 3. Ce qui reste est typé par sa position dans la semaine.
    evenements: List[Dict[str, Any]] = []
    compteur_semaine = 0
    for jour_prevu in jours_prevus:
        cle = (jour_prevu["mois"], jour_prevu["jour"])
        faites = heures_faites.get(cle, 0)
        manque = manques.get(cle, 0)
        curseur = compteur_semaine + faites
        while manque > 0 and curseur < duree_contrat_centiemes:
            tranche = min(1, manque, duree_contrat_centiemes - curseur)
            type_abs = (
                "absence_injustifiee_base"
                if curseur + tranche <= 3500
                else "absence_injustifiee_hs25"
            )
            evenements.append(
                {
                    "jour": jour_prevu["jour"],
                    "mois": jour_prevu["mois"],
                    "type": type_abs,
                    "heures": tranche / 100.0,
                }
            )
            curseur += tranche
            manque -= tranche
        compteur_semaine += faites
    return evenements


def analyser_horaires_du_mois(
    planned_data_all_months: List[Dict[str, Any]],
    actual_data_all_months: List[Dict[str, Any]],
    duree_hebdo_contrat: float,
    annee: int,
    mois: int,
    employee_name: str,
    *,
    modulation_weekly_hours: Dict[tuple[int, int], float] | None = None,
) -> List[Dict[str, Any]]:
    """
    Analyse les horaires et produit les événements de paie.
    La logique est robuste aux valeurs 'None' venant de la BDD.
    """
    log_payroll_debug(logger, f'INFO: Analyse des horaires pour {employee_name} - {mois:02d}/{annee}...')

    prevu_data = planned_data_all_months
    reel_data = actual_data_all_months
    if mois_sans_pointage(reel_data, annee=annee, mois=mois):
        log_payroll_debug(
            logger,
            f"INFO: Aucun pointage sur {mois:02d}/{annee} — pas de retenue d'absence "
            "(salaire de base conservé, pas d'heures sup. fictives).",
        )
    log_payroll_debug(logger, f'DEBUG: nb_jours_prevus={len(prevu_data)}, nb_jours_reels={len(reel_data)}')

    # Étape 1 : Regrouper les données par semaine ISO
    semaines = defaultdict(
        lambda: {"prevu": [], "reel": [], "jours_non_travailles": []}
    )
    for j in prevu_data:
        jour_date = date(j["annee"], j["mois"], j["jour"])
        cle_semaine = jour_date.isocalendar()[:2]
        if j.get("type") == "travail":
            semaines[cle_semaine]["prevu"].append(j)
        else:
            semaines[cle_semaine]["jours_non_travailles"].append(j)
    for j in reel_data:
        jour_date = date(j["annee"], j["mois"], j["jour"])
        cle_semaine = jour_date.isocalendar()[:2]
        semaines[cle_semaine]["reel"].append(j)

    # Étape 2 : Analyser chaque semaine
    evenements_finaux = []
    for cle_semaine, data in semaines.items():
        duree_hebdo_semaine = duree_hebdo_contrat
        if modulation_weekly_hours and cle_semaine in modulation_weekly_hours:
            duree_hebdo_semaine = modulation_weekly_hours[cle_semaine]
        duree_contrat_centiemes = int(duree_hebdo_semaine * 100)

        # On ajoute les jours non-travaillés sans heures réelles.
        # Exception : une demi-journée d'absence (quotite_absence < 1) coexiste
        # avec des heures pointées sur l'autre demi-journée — l'événement doit
        # quand même atteindre le bulletin (0,5 CP + matinée travaillée).
        for jour_prevu in data["jours_non_travailles"]:
            heures_reelles_ce_jour = any(
                j["jour"] == jour_prevu["jour"]
                and j["mois"] == jour_prevu["mois"]
                and (j.get("heures_faites") or 0) > 0  # Robuste à None
                for j in data["reel"]
            )
            try:
                quotite = float(jour_prevu.get("quotite_absence") or 1.0)
            except (TypeError, ValueError):
                quotite = 1.0
            if not heures_reelles_ce_jour or 0.0 < quotite < 1.0:
                evenements_finaux.append(jour_prevu)

        # Heures assimilées
        heures_assimilees = 0.0
        for jour_non_travaille in data["jours_non_travailles"]:
            if jour_non_travaille.get("type") in ["conges_payes", "ferie"]:
                heures_assimilees += (
                    jour_non_travaille.get("heures_prevues") or 0.0
                )  # Robuste à None

        compteur_heures_semaine_centiemes = int(heures_assimilees * 100)

        # Qualification des heures travaillées
        for jour_reel in sorted(data["reel"], key=lambda x: (x["mois"], x["jour"])):
            heures_jour_centiemes = int(
                (jour_reel.get("heures_faites") or 0.0) * 100
            )  # Robuste à None
            if heures_jour_centiemes <= 0:
                continue

            debut_compteur = compteur_heures_semaine_centiemes
            fin_compteur = compteur_heures_semaine_centiemes + heures_jour_centiemes
            if jour_reel.get("source_repli_planning"):
                # Le repli représente l'horaire prévu faute de pointage fiable :
                # il couvre les jours attendus sans créer d'HS/HC fictives.
                compteur_heures_semaine_centiemes = fin_compteur
                continue
            seuil_base_legal = 3500
            seuil_hs25_legal = 4300

            h_hs25 = max(
                0,
                min(fin_compteur, seuil_hs25_legal)
                - max(debut_compteur, duree_contrat_centiemes, seuil_base_legal),
            )
            h_hs50 = max(0, fin_compteur - max(debut_compteur, seuil_hs25_legal))

            # Heures complémentaires (temps partiel) : heures au-delà de la durée
            # contractuelle mais sous le seuil légal (3500 centièmes = 35 h).
            # Majoration à 10 % dans la limite du 1/10e du contrat, 25 % au-delà.
            if duree_contrat_centiemes < seuil_base_legal:
                seuil_hc10_centiemes = duree_contrat_centiemes + max(
                    1, duree_contrat_centiemes // 10
                )
                h_hc10 = max(
                    0,
                    min(fin_compteur, seuil_hc10_centiemes, seuil_base_legal)
                    - max(debut_compteur, duree_contrat_centiemes),
                )
                h_hc25 = max(
                    0,
                    min(fin_compteur, seuil_base_legal)
                    - max(debut_compteur, seuil_hc10_centiemes),
                )
                if h_hc10 > 0:
                    evenements_finaux.append(
                        {
                            "jour": jour_reel["jour"],
                            "mois": jour_reel["mois"],
                            "type": "travail_hc10",
                            "heures": h_hc10 / 100.0,
                        }
                    )
                if h_hc25 > 0:
                    evenements_finaux.append(
                        {
                            "jour": jour_reel["jour"],
                            "mois": jour_reel["mois"],
                            "type": "travail_hc25",
                            "heures": h_hc25 / 100.0,
                        }
                    )

            if h_hs25 > 0:
                evenements_finaux.append(
                    {
                        "jour": jour_reel["jour"],
                        "mois": jour_reel["mois"],
                        "type": "travail_hs25",
                        "heures": h_hs25 / 100.0,
                    }
                )
            if h_hs50 > 0:
                evenements_finaux.append(
                    {
                        "jour": jour_reel["jour"],
                        "mois": jour_reel["mois"],
                        "type": "travail_hs50",
                        "heures": h_hs50 / 100.0,
                    }
                )

            compteur_heures_semaine_centiemes = fin_compteur

        # Qualification des absences injustifiées : bilan de la semaine.
        # Une heure manquée un jour est compensée par une heure faite en plus
        # un autre jour de la même semaine, quel que soit l'ordre des jours.
        # C'est ce que retient le cabinet (Quadra, Colorplast juillet 2026 :
        # Fuckar, semaine du 6 juillet, −1,5 −4 +1 +2 → 2,5 h retenues). Retenir
        # jour par jour laissait les heures faites APRÈS un jour manqué sans
        # effet : ni payées, ni compensées, ni heures sup (semaine sous le
        # contrat). Retour Gaëlle du 14/09/2026.
        evenements_finaux.extend(
            _absences_injustifiees_de_la_semaine(
                data, reel_data, annee, duree_hebdo_semaine
            )
        )

    # Étape 3 : Agréger et filtrer uniquement le mois demandé
    agregats = defaultdict(float)
    jours_sans_heures = {}
    for ev in evenements_finaux:
        if ev.get("mois", mois) != mois:
            continue
        key = (ev["jour"], ev["type"])

        if ev.get("heures_prevues") is not None and "heures" not in ev:
            ev["heures"] = ev["heures_prevues"]

        if "heures" in ev:
            agregats[key] += ev.get("heures") or 0.0
        else:
            jours_sans_heures[key] = ev

    evenements_agreges: List[Dict[str, Any]] = []
    for k, v in agregats.items():
        jour_ev, type_ev = k[0], k[1]
        meta = _metadata_for_aggregated_event(
            evenements_finaux, mois, jour_ev, type_ev
        )
        if v <= 0 and not _conserver_evenement_a_zero_heure(type_ev, meta):
            continue
        ev_out: Dict[str, Any] = {
            "jour": jour_ev,
            "type": type_ev,
            "heures": round(v, 2),
        }
        ev_out.update(meta)
        evenements_agreges.append(ev_out)
    evenements_agreges.extend(jours_sans_heures.values())

    return sorted(evenements_agreges, key=lambda x: x["jour"])
