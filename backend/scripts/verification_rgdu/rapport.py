"""Sorties du rejeu : CSV nominatif (data/_rapports, hors git), résumés agrégés sans nom.

- `ecrire_csv` : une ligne par salarié et par mois, clé complète, avec les colonnes vides
  du classement final (étape 7 : `classement_final`, `regle`, `note_classement`) ;
- `resume_agrege` : comptes et impacts par société et pré-classement, puis par mois ;
- `couverture` : présence des trois colonnes (Quadra, loi, MARTINE) par société et par mois ;
- `detail_a_juger` : les lignes à juger, clé tronquée à 3 caractères, triées par impact.

`resume_agrege` et `couverture` ne portent aucune clé de salarié : ils peuvent aller dans un
rapport versionné. Impact : réduction cumulée de la colonne moins celle de la loi, sur les
cumuls de Quadra (`comparaison.impact_en_euros`) ; positif = plus de réduction que la loi.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, fields
from pathlib import Path

from scripts.verification_rgdu.comparaison import LigneComparee

PRECLASSEMENTS = ("identique", "arrondi", "a_juger_quadra", "erreur_eywai", "a_juger_les_deux",
                  "point_non_tranche", "donnee_manquante")
COLONNES_CLASSEMENT = ("classement_final", "regle", "note_classement")


def ecrire_csv(lignes: list[LigneComparee], chemin: Path, regles: list[str] | None = None) -> None:
    """`regles` : les ID de regles.md appliqués par la colonne loi, un par ligne (colonne
    `regles_loi`). Les colonnes du classement final restent vides."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    noms = [f.name for f in fields(LigneComparee)] + ["regles_loi", *COLONNES_CLASSEMENT]
    regles = regles if regles is not None else [""] * len(lignes)
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=noms)
        w.writeheader()
        for l, r in zip(lignes, regles, strict=True):
            w.writerow({**asdict(l), "regles_loi": r, **dict.fromkeys(COLONNES_CLASSEMENT, "")})


def _euros(x: float) -> str:
    return f"{x:.2f}"


def resume_agrege(lignes: list[LigneComparee]) -> str:
    par_classe: dict[tuple[str, str], list[LigneComparee]] = defaultdict(list)
    par_mois: dict[tuple[str, int], list[LigneComparee]] = defaultdict(list)
    for l in lignes:
        par_classe[(l.societe, l.preclassement)].append(l)
        par_mois[(l.societe, l.mois)].append(l)

    sortie = [
        "Impact : réduction cumulée de la colonne moins celle de la loi (positif = plus de réduction "
        "que la loi), en euros, sur les cumuls de Quadra.",
        "",
        "| Société | Pré-classement | Lignes | Impact Quadra (€) | Impact Quadra en valeur absolue (€) "
        "| Impact MARTINE (€) | Impact MARTINE en valeur absolue (€) |",
        "|---|---|---|---|---|---|---|",
    ]
    for (s, c), ls in sorted(par_classe.items()):
        iq = [l.impact_quadra for l in ls]
        ie = [l.impact_eywai for l in ls]
        sortie.append(f"| {s} | {c} | {len(ls)} | {_euros(sum(iq))} | {_euros(sum(map(abs, iq)))} "
                      f"| {_euros(sum(ie))} | {_euros(sum(map(abs, ie)))} |")

    sortie += ["", "| Société | Mois | Lignes | " + " | ".join(PRECLASSEMENTS)
               + " | Impact Quadra (€) | Impact MARTINE (€) |",
               "|---|---|---|" + "---|" * len(PRECLASSEMENTS) + "---|---|"]
    for (s, m), ls in sorted(par_mois.items()):
        comptes = " | ".join(str(sum(1 for l in ls if l.preclassement == c)) for c in PRECLASSEMENTS)
        sortie.append(f"| {s} | {m} | {len(ls)} | {comptes} | {_euros(sum(l.impact_quadra for l in ls))} "
                      f"| {_euros(sum(l.impact_eywai for l in ls))} |")
    return "\n".join(sortie) + "\n"


def couverture(lignes: list[LigneComparee]) -> str:
    par_mois: dict[tuple[str, int], list[LigneComparee]] = defaultdict(list)
    for l in lignes:
        par_mois[(l.societe, l.mois)].append(l)
    sortie = ["| Société | Mois | Lignes | Quadra (DSN) | Quadra (implicite) | Quadra absent | Loi "
              "| Loi, seconde lecture | MARTINE |",
              "|---|---|---|---|---|---|---|---|---|"]
    for (s, m), ls in sorted(par_mois.items()):
        dsn = sum(1 for l in ls if l.smic_quadra is not None and l.source_quadra == "dsn")
        imp = sum(1 for l in ls if l.smic_quadra is not None and l.source_quadra == "implicite")
        absent = sum(1 for l in ls if l.smic_quadra is None)
        loi = sum(1 for l in ls if l.smic_loi is not None)
        variante = sum(1 for l in ls if l.smic_loi_variante is not None)
        eywai = sum(1 for l in ls if l.smic_eywai is not None)
        sortie.append(f"| {s} | {m} | {len(ls)} | {dsn} | {imp} | {absent} | {loi} | {variante} | {eywai} |")
    return "\n".join(sortie) + "\n"


def _montant(x: float | None) -> str:
    return "" if x is None else _euros(x)


def detail_a_juger(lignes: list[LigneComparee]) -> str:
    """Les lignes ni « identique » ni « arrondi », clé tronquée à 3 caractères, triées par
    impact décroissant (le plus grand des deux en valeur absolue)."""
    a_juger = [l for l in lignes if l.preclassement not in ("identique", "arrondi")]
    a_juger.sort(key=lambda l: (-max(abs(l.impact_quadra), abs(l.impact_eywai)), l.societe, l.mois, l.cle))
    sortie = ["| Société | Clé | Mois | Pré-classement | SMIC Quadra | Source | SMIC loi | Seconde lecture "
              "| SMIC MARTINE | Impact Quadra (€) | Impact MARTINE (€) | Note |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for l in a_juger:
        note = l.note.replace("|", "/")
        sortie.append(f"| {l.societe} | {l.cle[:3]} | {l.mois} | {l.preclassement} | {_montant(l.smic_quadra)} "
                      f"| {l.source_quadra} | {_montant(l.smic_loi)} | {_montant(l.smic_loi_variante)} "
                      f"| {_montant(l.smic_eywai)} | {_euros(l.impact_quadra)} | {_euros(l.impact_eywai)} | {note} |")
    return "\n".join(sortie) + "\n"
