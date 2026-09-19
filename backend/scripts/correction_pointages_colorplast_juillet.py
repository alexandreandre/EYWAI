"""Colorplast, juillet 2026 sur le test : remettre le réel d'aplomb après l'import S27–S30.

Le 19/09/2026, quatre feuilles (S27 à S30) ont été importées en une fois sur le
test. Relues case par case (voir docs/colorplast-reprise-passation.md) :

- 24 cases ont été mal lues (glissement de colonne après le mardi 14 férié,
  « 16H » lu « 17H »), dont deux heures négatives chez Espinosa ; la
  transcription ci-dessous est ce que la feuille dit, pause de 30 min déduite
  au-delà de 6 h comme le fait l'import ;
- deux cases de Marion sont illisibles (10/07 barré, 17/07 raturé) : laissées
  telles quelles, à demander à Gaëlle ;
- le commit par lot écrivait les 29 et 30 juin de S27 sous les numéros 29 et 30
  de juillet (corrigé depuis dans `commit_service`). Avant l'import, le réel de
  juillet de ces cinq salariés était vide (instantané du 18/09) : on retire ces
  deux jours, à condition qu'ils portent encore la valeur de S27. Demory avait
  déjà 29 et 30 à 8,5 h : inchangé ;
- juin est un mois repris (bulletin Quadra), son réel est vide : on n'y écrit
  pas les deux jours de S27, ils sont seulement rappelés en fin de rapport.

Simulation par défaut ; `--apply` n'écrit que `actual_hours` (ni le prévu, ni
les cumuls) et relit pour contrôler. Rejouable. Les bulletins de juillet
(brouillons) ne sont pas régénérés ici.

Usage :
    python -m scripts.correction_pointages_colorplast_juillet            # simulation
    python -m scripts.correction_pointages_colorplast_juillet --apply    # écrit
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETE = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE, MOIS = 2026, 7

SALARIES = {
    "BUGNY": "f8e431a3-350b-471e-9b78-9bc9fd1ce8b9",
    "COTTE": "e6d1588d-6b4a-4ff4-992f-279cdadd3c46",
    "DEMORY": "c4b93225-bd1f-4d9e-9f70-ab408182e5c2",
    "ESPINOSA": "53c92e83-4a1a-4214-b30d-577cd1ab9d2d",
    "FUCKAR": "fb3ba0fd-ef02-4af9-a4fd-d72d503c161f",
    "GAUTHERON": "1c4cc8b6-5f55-4d71-bba5-5acb8fa3efd2",
}

# Jour de juillet → heures lues sur la feuille (seules les cases mal importées).
TRANSCRIPTION: dict[str, dict[int, float]] = {
    "BUGNY": {16: 9.5, 17: 5.0, 20: 9.5, 21: 9.5, 23: 9.5},
    "COTTE": {13: 8.5, 16: 8.5, 17: 6.5, 23: 8.5, 24: 4.0},
    "DEMORY": {22: 4.5, 24: 4.0},
    "ESPINOSA": {16: 10.0, 17: 6.5, 20: 9.5, 21: 9.5, 22: 9.5, 23: 10.0, 24: 4.5},
    "FUCKAR": {},
    "GAUTHERON": {3: 5.0, 9: 1.0, 22: 8.5, 23: 7.75, 24: 5.0},
}

ILLISIBLES = {
    "GAUTHERON": {10: "6h – fin barrée (import : 0)", 17: "6h45–11h raturé (import : 6,0)"},
}

# (29 juin, 30 juin) lus sur S27 : écrits à tort en juillet chez cinq salariés.
S27_FIN_JUIN: dict[str, tuple[float, float]] = {
    "BUGNY": (9.5, 9.5),
    "COTTE": (8.5, 8.5),
    "DEMORY": (8.5, 8.5),
    "ESPINOSA": (8.5, 10.5),
    "FUCKAR": (8.5, 8.5),
    "GAUTHERON": (8.5, 8.5),
}
REEL_DE_JUILLET_VIDE_AVANT_IMPORT = {"BUGNY", "COTTE", "ESPINOSA", "FUCKAR", "GAUTHERON"}


def appliquer_corrections(
    calendrier_reel: list[dict[str, Any]],
    corrections: dict[int, float],
    a_retirer: set[int],
) -> tuple[list[dict[str, Any]], list[tuple[int, float | None, float | None]]]:
    """Le calendrier réel corrigé et le journal (jour, avant, après).

    Une case corrigée absente du calendrier est créée en « travail » ; un jour
    à retirer absent ne produit rien : rejouer ne change plus rien.
    """
    par_jour = {int(d["jour"]): dict(d) for d in calendrier_reel if d.get("jour") is not None}
    journal: list[tuple[int, float | None, float | None]] = []
    for jour, heures in sorted(corrections.items()):
        entree = par_jour.get(jour)
        avant = entree.get("heures_faites") if entree else None
        if entree is not None and avant == heures:
            continue
        par_jour[jour] = {**(entree or {"type": "travail"}), "jour": jour, "heures_faites": heures}
        journal.append((jour, avant, heures))
    for jour in sorted(a_retirer):
        entree = par_jour.pop(jour, None)
        if entree is not None:
            journal.append((jour, entree.get("heures_faites"), None))
    journal.sort(key=lambda ligne: ligne[0])
    return [par_jour[j] for j in sorted(par_jour)], journal


def _jours_de_juin_a_retirer(nom: str, calendrier_reel: list[dict[str, Any]]) -> tuple[set[int], list[str]]:
    """Les 29 et 30 ne sont retirés que s'ils portent encore la valeur de S27."""
    if nom not in REEL_DE_JUILLET_VIDE_AVANT_IMPORT:
        return set(), []
    actuel = {int(d["jour"]): d.get("heures_faites") for d in calendrier_reel if d.get("jour") is not None}
    a_retirer: set[int] = set()
    alertes: list[str] = []
    for jour, attendu in zip((29, 30), S27_FIN_JUIN[nom]):
        if jour not in actuel:
            continue
        if actuel[jour] == attendu:
            a_retirer.add(jour)
        else:
            alertes.append(f"{nom} {jour}/07 porte {actuel[jour]} et non la valeur S27 {attendu} : laissé")
    return a_retirer, alertes


def _fmt(valeur: float | None) -> str:
    return "—" if valeur is None else f"{valeur:g}"


def main(appliquer: bool) -> int:
    from app.core.database import supabase

    reponse = (
        supabase.table("employee_schedules")
        .select("id, employee_id, actual_hours, updated_at")
        .in_("employee_id", list(SALARIES.values()))
        .eq("year", ANNEE)
        .eq("month", MOIS)
        .execute()
    )
    lignes = {str(r["employee_id"]): r for r in reponse.data or []}
    manquants = [nom for nom, eid in SALARIES.items() if eid not in lignes]
    if manquants:
        print(f"!! pas de ligne de juillet pour {', '.join(manquants)} — rien n'est fait")
        return 1

    print(f"{'Salarié':10s} {'Jour':>5s} {'Avant':>7s} {'Après':>7s}")
    print("-" * 34)
    a_ecrire: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    alertes: list[str] = []
    for nom, eid in SALARIES.items():
        ligne = lignes[eid]
        ah = dict(ligne.get("actual_hours") or {})
        reel = list(ah.get("calendrier_reel") or [])
        a_retirer, avertissements = _jours_de_juin_a_retirer(nom, reel)
        alertes.extend(avertissements)
        nouveau, journal = appliquer_corrections(reel, TRANSCRIPTION[nom], a_retirer)
        for jour, avant, apres in journal:
            print(f"{nom:10s} {jour:02d}/07 {_fmt(avant):>7s} {_fmt(apres):>7s}")
        if not journal:
            print(f"{nom:10s}   rien à changer")
        else:
            a_ecrire.append((nom, ligne, {**ah, "calendrier_reel": nouveau}))

    print()
    for nom, cases in ILLISIBLES.items():
        for jour, motif in cases.items():
            print(f"laissé tel quel  {nom} {jour:02d}/07 : {motif} — à demander à Gaëlle")
    for alerte in alertes:
        print(f"!! {alerte}")
    print("pour mémoire, non écrits (juin est repris de Quadra) — S27 29/06, 30/06 :")
    for nom, (j29, j30) in S27_FIN_JUIN.items():
        print(f"  {nom:10s} {j29:g} h, {j30:g} h")

    if not appliquer:
        print(f"\nSimulation : {len(a_ecrire)} calendrier(s) à écrire. Relancer avec --apply.")
        return 0

    print(f"\n--- Écriture de {len(a_ecrire)} calendrier(s) réel(s)")
    for nom, ligne, actual_hours in a_ecrire:
        supabase.table("employee_schedules").update({"actual_hours": actual_hours}).eq(
            "id", ligne["id"]
        ).execute()
        relu = (
            supabase.table("employee_schedules")
            .select("actual_hours")
            .eq("id", ligne["id"])
            .single()
            .execute()
        ).data
        if (relu or {}).get("actual_hours", {}).get("calendrier_reel") != actual_hours["calendrier_reel"]:
            print(f"  {nom:10s} !! relecture différente de ce qui a été écrit")
            return 1
        print(f"  {nom:10s} écrit et relu")
    print("Les bulletins de juillet (brouillons) restent à régénérer à la main.")
    return 0


if __name__ == "__main__":
    sys.exit(main(appliquer="--apply" in sys.argv[1:]))
