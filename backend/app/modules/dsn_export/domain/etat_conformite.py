"""État de conformité de la sortie DSN.

Un fichier incomplet qui se présente comme valide est plus dangereux qu'un
export absent : déposé tel quel, il est rejeté au mieux, accepté partiellement
au pire. Tant que tous les blocs ne sont pas produits, la génération le dit.

Le chantier et sa méthode de mesure sont décrits dans
``docs/superpowers/specs/2026-08-03-dsn-export-conformite-design.md``.
"""

from __future__ import annotations

from typing import List

# Blocs dont la conformité est établie par comparaison aux DSN du cabinet.
BLOCS_CONFORMES: List[str] = [
    "S10.G00.00 — envoi",
    "S10.G00.01 — émetteur",
    "S20.G00.05 — déclaration",
    "S20.G00.07 — contacts",
    "S21.G00.06 — entreprise",
    "S21.G00.11 — établissement",
    "S21.G00.30 — individu",
    "S21.G00.40 — contrat",
    "S90.G00.90 — total du fichier",
]

# Ce qui manque encore, dans l'ordre où le spec prévoit de le traiter.
BLOCS_MANQUANTS: List[str] = [
    "cotisations individuelles (S21.G00.81) : parts salariale et patronale "
    "émises en double, codes 071, 072, 102, 106 et 907 absents",
    "cotisations agrégées, bordereau et versement URSSAF "
    "(S21.G00.23, S21.G00.22, S21.G00.20)",
    "prévoyance : adhésion et affiliations (S21.G00.15, S21.G00.44, S21.G00.70)",
    "fins de contrat et arrêts de travail (S21.G00.62, S21.G00.65)",
    "salariés sortis encore déclarés le mois de leur solde",
]

DEPOSABLE = False

SUFFIXE_NON_DEPOSABLE = "_NON_DEPOSABLE"


def message_non_deposable() -> str:
    manquants = "\n".join(f"  - {bloc}" for bloc in BLOCS_MANQUANTS)
    return (
        "DSN incomplète : ne pas déposer sur net-entreprises.\n"
        "Blocs conformes : "
        + ", ".join(bloc.split(" — ")[0] for bloc in BLOCS_CONFORMES)
        + ".\nReste à produire :\n"
        + manquants
    )


def anomalie_non_deposable() -> dict:
    return {
        "type": "error",
        "message": message_non_deposable(),
        "severity": "blocking",
        "employee_id": None,
        "employee_name": None,
    }
