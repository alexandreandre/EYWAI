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

        # On ajoute les jours non-travaillés sans heures réelles
        for jour_prevu in data["jours_non_travailles"]:
            heures_reelles_ce_jour = any(
                j["jour"] == jour_prevu["jour"]
                and j["mois"] == jour_prevu["mois"]
                and (j.get("heures_faites") or 0) > 0  # Robuste à None
                for j in data["reel"]
            )
            if not heures_reelles_ce_jour:
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

        # Qualification des absences injustifiées
        compteur_heures_faites_semaine_centiemes = 0
        duree_contrat_centiemes_abs = int(duree_hebdo_semaine * 100)

        for jour_prevu in sorted(data["prevu"], key=lambda x: (x["mois"], x["jour"])):
            heures_prevues_jour_centiemes = int(
                (jour_prevu.get("heures_prevues") or 0.0) * 100
            )  # Robuste à None
            jour_annee = jour_prevu.get("annee", annee)
            jour_mois = jour_prevu["mois"]
            if mois_sans_pointage(reel_data, annee=jour_annee, mois=jour_mois):
                compteur_heures_faites_semaine_centiemes += heures_prevues_jour_centiemes
                continue

            jour_reel = next(
                (
                    j
                    for j in data["reel"]
                    if j["jour"] == jour_prevu["jour"]
                    and j["mois"] == jour_prevu["mois"]
                ),
                None,
            )
            if jour_reel is None:
                # Aucun pointage ce jour-là : on retient le prévu. Un jour sans
                # donnée n'est pas un jour d'absence — l'absence est un fait
                # constaté (zéro heure saisie, ou demande validée posée sur le
                # planning), pas un trou. Le repli `mois_sans_pointage` ci-dessus
                # ne couvre que les mois ENTIÈREMENT vides ; les calendriers
                # réels sont partiels (322 h pointées pour 1 113 prévues chez
                # Colorplast en janvier) et chaque jour manquant était retenu.
                compteur_heures_faites_semaine_centiemes += (
                    heures_prevues_jour_centiemes
                )
                continue

            heures_faites_jour_centiemes = int(
                (jour_reel.get("heures_faites") or 0.0) * 100
            )  # Robuste à None

            if heures_faites_jour_centiemes < heures_prevues_jour_centiemes:
                manque_centiemes = (
                    heures_prevues_jour_centiemes - heures_faites_jour_centiemes
                )
                curseur_centiemes = (
                    compteur_heures_faites_semaine_centiemes
                    + heures_faites_jour_centiemes
                )
                while manque_centiemes > 0:
                    if curseur_centiemes >= duree_contrat_centiemes_abs:
                        break
                    tranche = min(
                        1,
                        manque_centiemes,
                        duree_contrat_centiemes_abs - curseur_centiemes,
                    )
                    position_apres = curseur_centiemes + tranche
                    type_abs = (
                        "absence_injustifiee_base"
                        if position_apres <= 3500
                        else "absence_injustifiee_hs25"
                    )
                    evenements_finaux.append(
                        {
                            "jour": jour_prevu["jour"],
                            "mois": jour_prevu["mois"],
                            "type": type_abs,
                            "heures": tranche / 100.0,
                        }
                    )
                    curseur_centiemes += tranche
                    manque_centiemes -= tranche
            compteur_heures_faites_semaine_centiemes += heures_faites_jour_centiemes

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
        if v <= 0 and type_ev not in TYPES_SIGNIFICATIFS_A_ZERO_HEURE:
            continue
        ev_out: Dict[str, Any] = {
            "jour": jour_ev,
            "type": type_ev,
            "heures": round(v, 2),
        }
        ev_out.update(
            _metadata_for_aggregated_event(evenements_finaux, mois, jour_ev, type_ev)
        )
        evenements_agreges.append(ev_out)
    evenements_agreges.extend(jours_sans_heures.values())

    return sorted(evenements_agreges, key=lambda x: x["jour"])
