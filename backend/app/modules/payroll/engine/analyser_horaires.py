# moteur_paie/analyser_horaires.py
"""
Entrée fichier : charge calendriers depuis le disque puis délègue à la source de vérité
app.modules.payroll.application.analyzer.analyser_horaires_du_mois (signature in-memory).
"""
import json
import sys
from pathlib import Path
from datetime import date
from typing import Dict, Any, List
import argparse
import traceback


def analyser_horaires_du_mois(
    chemin_employe: Path, annee: int, mois: int, duree_hebdo_contrat: float
) -> List[Dict[str, Any]]:
    """
    Analyse les horaires à partir des fichiers calendriers du dossier employé.
    Délègue le cœur du calcul à app.modules.payroll.application.analyzer.
    """
    mois_prec = mois - 1 or 12
    annee_prec = annee - 1 if mois == 1 else annee
    mois_suiv = mois + 1 if mois < 12 else 1
    annee_suiv = annee + 1 if mois == 12 else annee

    fichiers = [
        (annee_prec, mois_prec),
        (annee, mois),
        (annee_suiv, mois_suiv)
    ]

    prevu_data = []
    reel_data = []
    for a, m in fichiers:
        cp = chemin_employe / 'calendriers' / f'{m:02d}.json'
        cr = chemin_employe / 'horaires' / f'{m:02d}.json'
        if cp.exists():
            for j in json.loads(cp.read_text(encoding='utf-8')).get('calendrier_prevu', []):
                j = {**j, 'annee': a, 'mois': m}
                prevu_data.append(j)
        if cr.exists():
            for j in json.loads(cr.read_text(encoding='utf-8')).get('calendrier_reel', []):
                j = {**j, 'annee': a, 'mois': m}
                reel_data.append(j)

    from app.modules.payroll.application.analyzer import analyser_horaires_du_mois as _analyser_in_memory

    return _analyser_in_memory(
        prevu_data,
        reel_data,
        duree_hebdo_contrat,
        annee,
        mois,
        chemin_employe.name,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyse les horaires prévus et réels pour générer un fichier d'événements de paie.")
    parser.add_argument("nom_employe", type=str, help="Le nom du dossier de l'employé.")
    parser.add_argument("--annee", type=int, default=date.today().year)
    parser.add_argument("--mois", type=int, default=date.today().month)
    args = parser.parse_args()

    try:
        chemin_employe = Path('data/employes') / args.nom_employe

        chemin_contrat = chemin_employe / 'contrat.json'
        if not chemin_contrat.exists():
            raise FileNotFoundError(f"Le fichier contrat.json est introuvable pour {args.nom_employe}")

        contrat_data = json.loads(chemin_contrat.read_text(encoding='utf-8'))
        duree_hebdo = contrat_data.get('contrat', {}).get('temps_travail', {}).get('duree_hebdomadaire')
        if not duree_hebdo:
            raise ValueError(f"La 'duree_hebdomadaire' n'est pas définie dans le contrat.json de {args.nom_employe}")

        evenements = analyser_horaires_du_mois(chemin_employe, args.annee, args.mois, duree_hebdo)

        output_path = chemin_employe / 'evenements_paie' / f'{args.mois:02d}.json'
        output_data = {
            "periode": {"annee": args.annee, "mois": args.mois},
            "calendrier_analyse": evenements
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Fichier d'événements généré avec succès : {output_path}", file=sys.stderr)

    except Exception as e:
        print(f"\nERREUR : {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
