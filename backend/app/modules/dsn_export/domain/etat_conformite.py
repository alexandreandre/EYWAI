"""État de conformité de la sortie DSN.

Un fichier incomplet qui se présente comme valide est plus dangereux qu'un
export absent : déposé tel quel, il est rejeté au mieux, accepté partiellement
au pire. Tant que le dépôt n'est pas ouvert, la génération le dit.

Le chantier et sa méthode de mesure sont décrits dans
``docs/superpowers/specs/2026-08-03-dsn-export-conformite-design.md``.

Lever le blocage (``DEPOSABLE = True``) est une décision d'Alexandre, pas un
effet de bord d'un correctif : ce module ne dit que l'état, à jour du 05/10/2026.
"""

from __future__ import annotations

from typing import List

# Ce que l'export produit déjà (chantier DSN des 03/08 au 05/10/2026), dit
# avec les mots de la gestionnaire de paie : elle lit ce texte à l'écran.
DEJA_PRODUIT: List[str] = [
    "envoi, déclaration, entreprise et établissement",
    "salariés et contrats",
    "rémunérations et cotisations individuelles",
    "bordereau et versements Urssaf, retraite complémentaire et impôt à la source",
    "prévoyance et mutuelle : adhésions et affiliations",
    "arrêts de travail, fins de contrat et autres suspensions",
]

# Ce qui reste avant d'ouvrir le dépôt.
RESTE_AVANT_DEPOT: List[str] = [
    "les versements trimestriels aux organismes de prévoyance et de mutuelle : "
    "pas encore produits",
    "les cotisations Urssaf qui ne figurent sur aucun bulletin (solde annuel, "
    "réduction ponctuelle) : absentes du bordereau",
    "une DSN complète contrôlée sans rejet par l'outil officiel DSN-VAL, "
    "pour chaque société",
]

DEPOSABLE = False

SUFFIXE_NON_DEPOSABLE = "_NON_DEPOSABLE"


def message_non_deposable() -> str:
    produit = "\n".join(f"  - {ligne}" for ligne in DEJA_PRODUIT)
    reste = "\n".join(f"  - {ligne}" for ligne in RESTE_AVANT_DEPOT)
    return (
        "DSN pas encore déposable : ne déposez pas ce fichier sur net-entreprises.\n"
        "Déjà produit par Martine :\n"
        + produit
        + "\nReste avant d'ouvrir le dépôt :\n"
        + reste
        + "\nEn attendant : déposez la DSN du mois comme avant, depuis votre "
        "ancien logiciel de paie. Si ce n'est pas possible, ouvrez un ticket "
        "(menu Support, module « Paie & Bulletins », urgence « Critique ») "
        "avant l'échéance de dépôt."
    )


def anomalie_non_deposable() -> dict:
    return {
        "type": "error",
        "message": message_non_deposable(),
        "severity": "blocking",
        "employee_id": None,
        "employee_name": None,
    }
