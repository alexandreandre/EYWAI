"""Colorplast : saisir la semaine 31 (27 au 31 juillet 2026) sur le test.

Cette semaine ouvre la fenêtre des variables d'août (27/07 → 23/08). Sans elle,
la paie d'août est bloquée. Cinq salariés l'attendent : Girerd et Demory ont
déjà des jours en base (voir le rapport de contrôle en fin d'exécution).

Source : `data/colorplast/pointages/2026-08/semaine-31.jpeg`, feuille
manuscrite de Gaëlle, relue case par case après redressement de la photo
(la feuille est couchée dans la photo). Les prénoms de la feuille valent
HUGO = Fuckar, MICHEL = Bugny, ANTHONY = Espinosa, LEO = Cotte,
AURELIEN = Demory (sorti le 24/07, ligne vide), MARION = Gautheron.

Marion n'a pas d'horaire dans les cases du lundi au jeudi : une accolade sous
ces quatre colonnes porte « 6h - 15h ». C'est ce qui est repris ici.

Les heures ne sont PAS écrites en dur : la transcription garde les horaires de
la feuille et le script applique `calculate_hours_from_range` avec les réglages
de la société lus en base, exactement comme le ferait un import depuis l'écran.
Pour Colorplast : 30 minutes de pause déduites au-delà de 6 h de présence.

Une case vide donne 0 h, comme à l'import. C'est le cas du vendredi d'Anthony,
et cela lui coûte des heures — le rapport le chiffre : à faire confirmer par
Gaëlle.

Simulation par défaut ; `--apply` n'écrit que `actual_hours` (ni le prévu, ni
les cumuls) et relit pour contrôler. Rejouable : relancer ne change plus rien.

Usage :
    python -m scripts.pointages_colorplast_semaine_31            # simulation
    python -m scripts.pointages_colorplast_semaine_31 --apply    # écrit
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SOCIETE = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"
ANNEE, MOIS = 2026, 7
JOURS = (27, 28, 29, 30, 31)  # lundi 27 → vendredi 31 juillet 2026

# Nom de famille → jour de juillet → (DEBUT, FIN) tels qu'écrits sur la feuille.
# None : case vide.
FEUILLE: dict[str, dict[int, tuple[str, str] | None]] = {
    "FUCKAR": {
        27: ("7h", "16h"),
        28: ("7h", "16h"),
        29: ("10h", "17h30"),
        30: ("7h", "19h30"),
        31: ("7h", "12h"),
    },
    "BUGNY": {
        27: ("7h", "17h"),
        28: ("7h", "17h"),
        29: ("7h", "17h"),
        30: ("7h", "17h"),
        31: ("7h", "12h"),
    },
    "ESPINOSA": {
        27: ("6h", "16h"),
        28: ("6h", "16h"),
        29: ("6h", "16h"),
        30: ("6h", "15h"),
        31: None,
    },
    "COTTE": {
        27: ("7h", "16h"),
        28: ("7h", "16h"),
        29: ("7h", "16h"),
        30: ("7h", "16h"),
        31: ("7h", "12h"),
    },
    "GAUTHERON": {
        # Accolade « 6h - 15h » sous les colonnes lundi à jeudi.
        27: ("6h", "15h"),
        28: ("6h", "15h"),
        29: ("6h", "15h"),
        30: ("6h", "15h"),
        31: ("7h", "11h"),
    },
}

# Déjà pointés : on ne les touche pas, on les contrôle seulement.
DEJA_EN_BASE = ("GIRERD", "DEMORY")


def heures_de_la_feuille(plage: tuple[str, str] | None, settings: Any) -> float:
    """Heures retenues pour une case, à l'identique de l'import écran."""
    from app.modules.schedules.application.handwritten_weekly import (
        calculate_hours_from_range,
    )

    if plage is None:
        return 0.0
    heures = calculate_hours_from_range(plage[0], plage[1], settings=settings)
    if heures is None:
        raise ValueError(f"plage illisible : {plage}")
    return heures


def calendrier_avec_la_semaine(
    calendrier_reel: list[dict[str, Any]],
    semaine: dict[int, float],
) -> tuple[list[dict[str, Any]], list[tuple[int, float | None, float]]]:
    """Le calendrier réel complété et le journal (jour, avant, après)."""
    par_jour = {
        int(d["jour"]): dict(d)
        for d in calendrier_reel
        if d.get("jour") is not None
    }
    journal: list[tuple[int, float | None, float]] = []
    for jour, heures in sorted(semaine.items()):
        entree = par_jour.get(jour)
        avant = entree.get("heures_faites") if entree else None
        if entree is not None and avant == heures:
            continue
        par_jour[jour] = {
            **(entree or {"type": "travail"}),
            "jour": jour,
            "heures_faites": heures,
        }
        journal.append((jour, avant, heures))
    return [par_jour[j] for j in sorted(par_jour)], journal


def bilan_de_la_semaine(
    semaine: dict[int, float], prevu: dict[int, float]
) -> tuple[float, float]:
    """Heures faites et heures prévues sur les cinq jours."""
    return (
        round(sum(semaine.values()), 2),
        round(sum(prevu.get(j, 0.0) for j in JOURS), 2),
    )


def _fmt(valeur: float | None) -> str:
    return "—" if valeur is None else f"{valeur:g}"


def main(appliquer: bool) -> int:
    from app.core.database import supabase
    from app.modules.schedules.infrastructure.punch_accounting_repository import (
        get_settings,
    )

    settings = get_settings(SOCIETE)
    if not settings.enabled:
        print(
            "!! la comptabilisation des pointages est désactivée pour la société :\n"
            "   les heures seraient BRUTES (aucune pause déduite). Rien n'est fait."
        )
        return 1
    print(
        f"Pause de la société : {settings.default_break_deduct_minutes} min "
        f"au-delà de {settings.break_threshold_minutes / 60:g} h de présence.\n"
    )

    salaries = {
        str(r["last_name"]).upper(): str(r["id"])
        for r in (
            supabase.table("employees")
            .select("id, last_name")
            .eq("company_id", SOCIETE)
            .execute()
        ).data
        or []
    }
    manquants = [nom for nom in FEUILLE if nom not in salaries]
    if manquants:
        print(f"!! pas de salarié nommé {', '.join(manquants)} — rien n'est fait")
        return 1

    lignes = {
        str(r["employee_id"]): r
        for r in (
            supabase.table("employee_schedules")
            .select("id, employee_id, planned_calendar, actual_hours")
            .eq("company_id", SOCIETE)
            .eq("year", ANNEE)
            .eq("month", MOIS)
            .execute()
        ).data
        or []
    }
    sans_ligne = [nom for nom in FEUILLE if salaries[nom] not in lignes]
    if sans_ligne:
        print(f"!! pas de ligne de juillet pour {', '.join(sans_ligne)} — rien n'est fait")
        return 1

    print(f"{'Salarié':11s} {'Jour':>6s} {'Plage':>13s} {'Avant':>7s} {'Après':>7s}")
    print("-" * 48)
    a_ecrire: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    bilans: list[str] = []
    for nom, cases in FEUILLE.items():
        ligne = lignes[salaries[nom]]
        semaine = {j: heures_de_la_feuille(cases[j], settings) for j in JOURS}
        ah = dict(ligne.get("actual_hours") or {})
        reel = list(ah.get("calendrier_reel") or [])
        nouveau, journal = calendrier_avec_la_semaine(reel, semaine)
        for jour, avant, apres in journal:
            plage = cases[jour]
            libelle = "(vide)" if plage is None else f"{plage[0]}→{plage[1]}"
            print(
                f"{nom:11s} {jour:02d}/07 {libelle:>13s} "
                f"{_fmt(avant):>7s} {_fmt(apres):>7s}"
            )
        if not journal:
            print(f"{nom:11s}   rien à changer")
        else:
            a_ecrire.append((nom, ligne, {**ah, "calendrier_reel": nouveau}))

        prevu = {
            int(d["jour"]): float(d.get("heures_prevues") or 0.0)
            for d in (ligne.get("planned_calendar") or {}).get("calendrier_prevu") or []
            if d.get("jour") is not None
        }
        faites, attendues = bilan_de_la_semaine(semaine, prevu)
        ecart = round(faites - attendues, 2)
        bilans.append(
            f"  {nom:11s} {faites:5.2f} h faites / {attendues:5.2f} h prévues "
            f"({ecart:+.2f})"
        )

    print("\nBilan de la semaine 31")
    for ligne_bilan in bilans:
        print(ligne_bilan)

    print("\nContrôle des salariés non repris sur la feuille")
    for nom in DEJA_EN_BASE:
        eid = salaries.get(nom)
        ligne = lignes.get(eid or "")
        if ligne is None:
            print(f"  {nom:11s} pas de ligne de juillet")
            continue
        reel = (ligne.get("actual_hours") or {}).get("calendrier_reel") or []
        jours = {
            int(d["jour"]): d.get("heures_faites")
            for d in reel
            if d.get("jour") is not None and int(d["jour"]) in JOURS
        }
        detail = ", ".join(f"{j:02d}/07 {_fmt(h)}" for j, h in sorted(jours.items()))
        print(f"  {nom:11s} {detail or 'aucun jour du 27 au 31'}")

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
        if (relu or {}).get("actual_hours", {}).get("calendrier_reel") != actual_hours[
            "calendrier_reel"
        ]:
            print(f"  {nom:11s} !! relecture différente de ce qui a été écrit")
            return 1
        print(f"  {nom:11s} écrit et relu")
    return 0


if __name__ == "__main__":
    sys.exit(main(appliquer="--apply" in sys.argv[1:]))
