# moteur_paie/analyser_jours_forfait.py
"""
Module d'analyse des jours travaillés pour les employés en forfait jour.

Ce module analyse les calendriers prévus et réels pour les employés en forfait jour,
où les données sont stockées en jours (0/1) plutôt qu'en heures.
"""

import sys
from datetime import date
from typing import Dict, Any, List
from collections import defaultdict
import json


def analyser_jours_forfait_du_mois(
    planned_data_all_months: List[Dict[str, Any]],
    actual_data_all_months: List[Dict[str, Any]],
    annee: int,
    mois: int,
    employee_name: str,
    date_debut_periode: date | None = None,
    date_fin_periode: date | None = None,
) -> List[Dict[str, Any]]:
    """
    Analyse les jours travaillés pour un employé en forfait jour.

    Pour le forfait jour :
    - heures_prevues = 1 → Jour prévu (travaillé)
    - heures_prevues = 0 → Jour non prévu (non travaillé)
    - heures_faites = 1 → Jour travaillé (fait)
    - heures_faites = 0 → Jour non travaillé (fait)

    Args:
        planned_data_all_months: Liste des jours prévus (M-1, M, M+1)
        actual_data_all_months: Liste des jours réels (M-1, M, M+1)
        annee: Année du mois à analyser
        mois: Mois à analyser
        employee_name: Nom de l'employé (pour les logs)
        date_debut_periode: Date de début de la période de paie (optionnel)
        date_fin_periode: Date de fin de la période de paie (optionnel)

    Returns:
        Liste d'événements de paie adaptés au forfait jour
        Si date_debut_periode et date_fin_periode sont fournies, filtre selon la période.
        Sinon, filtre uniquement le mois demandé (comportement par défaut).
    """
    print(
        f"INFO: Analyse des jours forfait pour {employee_name} - {mois:02d}/{annee}...",
        file=sys.stderr,
    )

    prevu_data = planned_data_all_months
    reel_data = actual_data_all_months
    print(
        f"DEBUG: nb_jours_prevus={len(prevu_data)}, nb_jours_reels={len(reel_data)}",
        file=sys.stderr,
    )

    # Debug : Afficher la répartition par mois
    if date_debut_periode and date_fin_periode:
        print(
            f"DEBUG: Période de paie : du {date_debut_periode.strftime('%d/%m/%Y')} au {date_fin_periode.strftime('%d/%m/%Y')}",
            file=sys.stderr,
        )
        prevu_par_mois = {}
        reel_par_mois = {}
        for j in prevu_data:
            m = j.get("mois", "?")
            prevu_par_mois[m] = prevu_par_mois.get(m, 0) + 1
        for j in reel_data:
            m = j.get("mois", "?")
            reel_par_mois[m] = reel_par_mois.get(m, 0) + 1
        print(f"DEBUG: Jours prévus par mois: {prevu_par_mois}", file=sys.stderr)
        print(f"DEBUG: Jours réels par mois: {reel_par_mois}", file=sys.stderr)

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
        # On ajoute les jours non-travaillés prévus (congés, fériés, etc.)
        for jour_prevu in data["jours_non_travailles"]:
            jour_travaille_reel = any(
                j["jour"] == jour_prevu["jour"]
                and j["mois"] == jour_prevu["mois"]
                and (j.get("heures_faites") or 0) == 1  # Jour travaillé = 1
                for j in data["reel"]
            )
            if not jour_travaille_reel:
                # Le jour non travaillé prévu n'a pas été travaillé → événement valide
                evenements_finaux.append(jour_prevu)

        # Traitement des jours travaillés réels
        for jour_reel in sorted(data["reel"], key=lambda x: (x["mois"], x["jour"])):
            heures_faites = jour_reel.get("heures_faites", 0)

            # En forfait jour, heures_faites = 1 signifie "jour travaillé"
            if heures_faites != 1:
                continue

            # Vérifier si ce jour était prévu comme jour travaillé
            jour_prevu = next(
                (
                    j
                    for j in data["prevu"]
                    if j["jour"] == jour_reel["jour"] and j["mois"] == jour_reel["mois"]
                ),
                None,
            )

            heures_prevues = jour_prevu.get("heures_prevues", 0) if jour_prevu else 0

            # Si le jour était prévu (heures_prevues = 1), c'est un jour travaillé normal
            if heures_prevues == 1:
                evenements_finaux.append(
                    {
                        "jour": jour_reel["jour"],
                        "mois": jour_reel["mois"],
                        "annee": jour_reel.get("annee", annee),
                        "type": "travail_base",
                        "heures": 1.0,  # 1 jour travaillé
                    }
                )
            else:
                # Jour travaillé mais non prévu → jour supplémentaire (rare en forfait jour)
                # On le traite comme un jour travaillé normal
                evenements_finaux.append(
                    {
                        "jour": jour_reel["jour"],
                        "mois": jour_reel["mois"],
                        "annee": jour_reel.get("annee", annee),
                        "type": "travail_base",
                        "heures": 1.0,
                    }
                )

        # Traitement des absences (jours prévus mais non travaillés)
        for jour_prevu in sorted(data["prevu"], key=lambda x: (x["mois"], x["jour"])):
            heures_prevues = jour_prevu.get("heures_prevues", 0)

            # Seulement les jours prévus comme travaillés (heures_prevues = 1)
            if heures_prevues != 1:
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

            heures_faites = jour_reel.get("heures_faites", 0) if jour_reel else 0

            # Si le jour était prévu mais pas fait → absence
            if heures_faites != 1:
                # Déterminer le type d'absence selon le type du jour prévu
                type_jour = jour_prevu.get("type", "travail")

                if type_jour == "travail":
                    # Absence injustifiée (jour prévu comme travaillé mais non fait)
                    ev_absence = {
                        "jour": jour_prevu["jour"],
                        "mois": jour_prevu["mois"],
                        "annee": jour_prevu.get("annee", annee),
                        "type": "absence_injustifiee_base",
                        "heures": 1.0,  # 1 jour d'absence
                    }
                    evenements_finaux.append(ev_absence)
                    # Debug pour les absences de janvier/février
                    if ev_absence["mois"] in [1, 2]:
                        print(
                            f"DEBUG: Absence détectée : {ev_absence['jour']:02d}/{ev_absence['mois']:02d}/{ev_absence['annee']}",
                            file=sys.stderr,
                        )
                # Les autres types (congés, fériés) sont déjà gérés dans jours_non_travailles

    # Étape 3 : Agréger et filtrer selon la période de paie ou le mois
    agregats = defaultdict(float)
    jours_sans_heures = {}

    for ev in evenements_finaux:
        # Construire la date complète de l'événement
        ev_annee = ev.get("annee", annee)
        ev_mois = ev.get("mois", mois)
        ev_jour = ev.get("jour")

        if ev_jour is None:
            continue

        ev_date = date(ev_annee, ev_mois, ev_jour)

        # Filtrer selon la période de paie si fournie, sinon selon le mois
        if date_debut_periode and date_fin_periode:
            # Filtrer selon la période de paie (peut s'étendre sur plusieurs mois)
            if not (date_debut_periode <= ev_date <= date_fin_periode):
                if "absence" in ev.get("type", ""):
                    print(
                        f"DEBUG: Événement d'absence exclu (hors période) : {ev_date.strftime('%d/%m/%Y')} (événement: {ev.get('type')})",
                        file=sys.stderr,
                    )
                continue
        else:
            # Comportement par défaut : filtrer uniquement le mois demandé
            if ev_mois != mois:
                continue

        # Clé d'agrégation incluant jour, mois, année et type pour préserver l'information du mois
        key = (ev["jour"], ev_mois, ev_annee, ev["type"])

        # Si l'événement a déjà un champ 'heures', on l'utilise
        if "heures" in ev:
            agregats[key] += ev.get("heures", 0.0)
        elif ev.get("heures_prevues") is not None:
            # Sinon, on utilise heures_prevues si disponible
            ev["heures"] = ev["heures_prevues"]
            agregats[key] += ev.get("heures", 0.0)
        else:
            # Jours sans heures (weekends, etc.) - préserver mois et année
            jours_sans_heures[key] = {**ev, "mois": ev_mois, "annee": ev_annee}

    # Créer la liste finale des événements agrégés avec mois et année
    evenements_agreges = [
        {"jour": k[0], "mois": k[1], "annee": k[2], "type": k[3], "heures": round(v, 2)}
        for k, v in agregats.items()
        if v > 0
    ]
    evenements_agreges.extend(jours_sans_heures.values())

    # Debug : Compter les absences par mois
    absences_par_mois = {}
    for ev in evenements_agreges:
        if "absence" in ev.get("type", ""):
            m = ev.get("mois", "?")
            absences_par_mois[m] = absences_par_mois.get(m, 0) + 1

    if absences_par_mois:
        print(
            f"DEBUG: Absences détectées par mois: {absences_par_mois}", file=sys.stderr
        )

    print(
        f"DEBUG: evenements_agreges={len(evenements_agreges)} événements",
        file=sys.stderr,
    )
    return sorted(
        evenements_agreges,
        key=lambda x: (x.get("annee", annee), x.get("mois", mois), x.get("jour", 0)),
    )


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Analyse les jours travaillés pour un employé en forfait jour."
    )
    parser.add_argument("nom_employe", type=str, help="Le nom du dossier de l'employé.")
    parser.add_argument("--annee", type=int, default=date.today().year)
    parser.add_argument("--mois", type=int, default=date.today().month)
    args = parser.parse_args()

    try:
        chemin_employe = Path("data/employes") / args.nom_employe

        # Charger les données prévues et réelles
        chemin_calendrier_prevu = (
            chemin_employe / "calendriers" / f"{args.mois:02d}.json"
        )
        chemin_horaires_reels = chemin_employe / "horaires" / f"{args.mois:02d}.json"

        if not chemin_calendrier_prevu.exists():
            raise FileNotFoundError(
                f"Le fichier calendrier prévu est introuvable pour {args.nom_employe}"
            )

        prevu_data = json.loads(
            chemin_calendrier_prevu.read_text(encoding="utf-8")
        ).get("calendrier_prevu", [])
        reel_data = []
        if chemin_horaires_reels.exists():
            reel_data = json.loads(
                chemin_horaires_reels.read_text(encoding="utf-8")
            ).get("calendrier_reel", [])

        # Ajouter les informations d'année et mois
        for j in prevu_data:
            j["annee"] = args.annee
            j["mois"] = args.mois
        for j in reel_data:
            j["annee"] = args.annee
            j["mois"] = args.mois

        evenements = analyser_jours_forfait_du_mois(
            prevu_data, reel_data, args.annee, args.mois, args.nom_employe
        )

        output_path = chemin_employe / "evenements_paie" / f"{args.mois:02d}.json"
        output_data = {
            "periode": {"annee": args.annee, "mois": args.mois},
            "calendrier_analyse": evenements,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(
            f"✅ Fichier d'événements généré avec succès : {output_path}",
            file=sys.stderr,
        )

    except Exception as e:
        print(f"\nERREUR : {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
