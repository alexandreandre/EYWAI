"""Feuilles de pointage de la fenêtre de juin 2026 de Colorplast, et leur pose.

Lues sur `data/colorplast/pointages/2026-06/semaine-22.pdf` à `semaine-25.pdf`,
avec la règle de Gaëlle annotée sur la feuille S03 de janvier : heures = fin −
début − 0,5 h de pause quand la journée dépasse 6 h. Prénoms → salariés :
Hugo = Fuckar, Michel = Bugny, Anthony = Espinosa, Léo = Cotte, Aurélien =
Demory, Marion = Gautheron. Girerd (cadre) n'a pas de feuille : planning repris
tel quel.

La fenêtre de juin va du 25/05 au 21/06 : la semaine 22 vit dans le calendrier
de mai, les trois autres dans celui de juin. Seules les heures viennent des
feuilles. Les absences (Demory le 08/06, Gautheron le 10/06), l'accident du
travail de Demory (jusqu'au 29/05) et la journée de solidarité du 25/05 — un
lundi de Pentecôte férié, travaillé 7 h par Bugny et Cotte, posé en congé chez
Espinosa, Gautheron et Girerd, ni travaillé ni posé chez Fuckar — restent ceux
du setup et du calendrier prévu.

Un jour absent du dictionnaire = pas de pointage (neutre) : les feuilles
blanches de Demory (S22, S23, du 10 au 12/06, dont une case sans heure de fin
le mercredi 10) et le lundi de Pentecôte de Fuckar.

Le classeur du cabinet (`data/colorplast/variables/2026-06/detail-heures-sup-
06-2026-colorplast.xlsx`) porte les mêmes journées pour S22 à S24 — même règle
de pause, à deux lectures près (Fuckar mardi 26/05 compté 1 h au lieu de 0,5 ;
Cotte ses vendredis 7h–15h comptés 7 h au lieu de 7,5) — et ses colonnes S25
sont vides. Voir `scripts/colorplast_feuilles_juin_test.py` pour la pose et le
contrôle, et `docs/colorplast-juin-2026-ligne-a-ligne.md` pour le compte rendu.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from datetime import date

from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.colorplast_setup import _clear_actual

YEAR, MOIS = 2026, 6
#: Jours de chaque mois qui appartiennent à la fenêtre du 25/05 au 21/06.
JOURS_DE_LA_FENETRE = {5: range(25, 32), 6: range(1, 22)}
#: Contrat de 39 h : la 40ᵉ à la 43ᵉ heure de la semaine à 25 %, au-delà à 50 %.
DUREE_CONTRAT, SEUIL_50 = 39.0, 43.0

#: Heures nettes par jour lues sur les feuilles ((mois, jour) → heures).
FEUILLES: dict[str, dict[tuple[int, int], float]] = {
    "BUGNY": {
        (5, 25): 7.0, (5, 26): 8.0, (5, 27): 9.5, (5, 28): 9.5, (5, 29): 5.0,      # S22 : 39 (lundi 7h–14h30, journée de solidarité)
        (6, 1): 9.5, (6, 2): 9.5, (6, 3): 9.5, (6, 4): 9.5, (6, 5): 5.0,           # S23 : 43
        (6, 8): 9.5, (6, 9): 9.5, (6, 10): 9.5, (6, 11): 9.5, (6, 12): 8.5,        # S24 : 46,5 (vendredi 7h–16h)
        (6, 15): 9.5, (6, 16): 9.5, (6, 17): 9.5, (6, 18): 9.5, (6, 19): 8.5,      # S25 : 46,5
    },
    "ESPINOSA": {
        (5, 26): 9.0, (5, 27): 10.5, (5, 28): 9.5, (5, 29): 5.5,                   # S22 : 34,5 (lundi en congé)
        (6, 1): 10.5, (6, 2): 10.5, (6, 3): 7.0, (6, 4): 10.0, (6, 5): 6.0,        # S23 : 44 (mercredi 11h30–19h)
        (6, 8): 9.5, (6, 9): 10.0, (6, 10): 10.08, (6, 11): 10.5, (6, 12): 5.0,    # S24 : 45,08 (mercredi 6h45–17h20)
        (6, 15): 10.0, (6, 16): 10.0, (6, 17): 11.0, (6, 18): 10.5, (6, 19): 5.5,  # S25 : 47
    },
    "FUCKAR": {
        (5, 26): 9.0, (5, 27): 9.5, (5, 28): 8.5, (5, 29): 5.0,                    # S22 : 32 (lundi vide)
        (6, 1): 8.5, (6, 2): 11.5, (6, 3): 8.5, (6, 4): 10.5, (6, 5): 7.0,         # S23 : 46 (mardi 7h–19h, vendredi 7h30–15h)
        (6, 8): 5.0, (6, 9): 10.0, (6, 10): 8.5, (6, 11): 9.5, (6, 12): 7.0,       # S24 : 40 (lundi 13h–18h)
        (6, 15): 7.5, (6, 16): 10.0, (6, 17): 9.0, (6, 18): 8.0, (6, 19): 8.5,     # S25 : 43
    },
    "COTTE": {
        (5, 25): 7.0, (5, 26): 8.5, (5, 27): 8.5, (5, 28): 8.5, (5, 29): 5.0,      # S22 : 37,5 (lundi 7h–14h30, journée de solidarité)
        (6, 1): 8.5, (6, 2): 8.5, (6, 3): 8.5, (6, 4): 8.5, (6, 5): 7.5,           # S23 : 41,5 (vendredi 7h–15h)
        (6, 8): 8.5, (6, 9): 8.5, (6, 10): 8.5, (6, 11): 8.5, (6, 12): 7.5,        # S24 : 41,5
        (6, 15): 8.5, (6, 16): 8.5, (6, 17): 8.5, (6, 18): 8.5, (6, 19): 8.5,      # S25 : 42,5 (vendredi 7h–16h)
    },
    "GAUTHERON": {
        (5, 26): 9.5, (5, 27): 8.5, (5, 28): 8.5, (5, 29): 5.0,                    # S22 : 31,5 (lundi en congé)
        (6, 1): 9.0, (6, 2): 8.5, (6, 3): 8.0, (6, 4): 9.0, (6, 5): 5.0,           # S23 : 39,5
        (6, 8): 8.5, (6, 9): 9.0, (6, 11): 8.5, (6, 12): 5.0,                      # S24 : 31 (absente le mercredi 10)
        (6, 15): 8.5, (6, 16): 8.5, (6, 17): 8.5, (6, 18): 8.5, (6, 19): 5.0,      # S25 : 39
    },
    "DEMORY": {
        # S22 : accident du travail jusqu'au 29/05. S23 : feuille blanche.
        (6, 8): 0.0, (6, 9): 8.5,                                                  # S24 : lundi 8 barré (pointé absent), blanc du 10 au 12
        (6, 15): 8.5, (6, 16): 8.5, (6, 17): 8.5, (6, 18): 8.5, (6, 19): 5.0,      # S25 : 39
    },
}


def heures_par_semaine(nom: str) -> dict[int, float]:
    """Total pointé de chaque semaine ISO (numéro de semaine → heures)."""
    totaux: dict[int, float] = defaultdict(float)
    for (mois, jour), heures in FEUILLES[nom].items():
        totaux[date(YEAR, mois, jour).isocalendar()[1]] += heures
    return {semaine: round(total, 2) for semaine, total in sorted(totaux.items())}


def heures_sup_attendues(nom: str) -> tuple[float, float]:
    """Ce que la règle hebdomadaire donne sur les feuilles : (à 25 %, à 50 %).

    Rien n'est assimilé à du travail dans ces quatre semaines : le congé et le
    férié du 25/05 sont à 0 h prévue au calendrier, et une absence non payée ne
    l'est jamais. Le compteur d'une semaine est donc son seul total pointé.
    """
    hs25 = hs50 = 0.0
    for total in heures_par_semaine(nom).values():
        hs25 += min(max(total - DUREE_CONTRAT, 0.0), SEUIL_50 - DUREE_CONTRAT)
        hs50 += max(total - SEUIL_50, 0.0)
    return round(hs25, 2), round(hs50, 2)


def poser_les_feuilles(emps: dict) -> None:
    """Écrit les journées pointées au calendrier réel de mai (25 au 29) et de juin.

    Les jours prévus en férié ou en congé sans heure pointée sont recopiés tels
    quels, comme en janvier ; une journée pointée sur un férié (le 25/05 de
    Bugny et de Cotte) est écrite en travail. Les heures sup posées en saisie
    par le setup sont ensuite effacées : le moteur doit les retrouver seul.
    """
    for nom, heures in FEUILLES.items():
        emp = emps[nom]
        postes = []
        for mois, jours_fenetre in JOURS_DE_LA_FENETRE.items():
            sched = (
                supabase.table("employee_schedules").select("id, planned_calendar, actual_hours")
                .match({"employee_id": emp["id"], "year": YEAR, "month": mois}).single().execute()
            ).data
            planned = sched.get("planned_calendar") or {}
            par_jour = {int(j["jour"]): j for j in planned.get("calendrier_prevu", [])}
            reel = []
            for jour in sorted(par_jour):
                if jour not in jours_fenetre:
                    continue
                prevu = par_jour[jour]
                if (mois, jour) in heures:
                    reel.append({"jour": jour, "type": "travail", "heures_faites": heures[(mois, jour)]})
                elif prevu.get("type") == "ferie":
                    reel.append({"jour": jour, "type": "ferie", "heures_faites": None})
                elif prevu.get("type") == "conges_payes":
                    reel.append({"jour": jour, "type": "conge", "heures_faites": 0.0})
            actual = copy.deepcopy(sched.get("actual_hours") or {})
            actual["periode"] = {"mois": mois, "annee": YEAR}
            actual["calendrier_reel"] = reel
            supabase.table("employee_schedules").update({"actual_hours": actual}).eq("id", sched["id"]).execute()
            postes.append(f"{len([r for r in reel if r['type'] == 'travail'])} j. en {mois:02d}")
        print(f"  {nom:10s} : {', '.join(postes)} pointés posés")
    # Les heures sup du setup (lues sur les bulletins Quadra) laissent la place aux feuilles.
    for nom, emp in emps.items():
        supabase.table("monthly_inputs").delete().match(
            {"employee_id": emp["id"], "year": YEAR, "month": MOIS}
        ).ilike("name", "%suppl%").execute()


def effacer_les_feuilles(emps: dict) -> None:
    """Vide le calendrier réel de mai et de juin : la base repart du planning."""
    admin = get_supabase_admin_client()
    for nom in FEUILLES:
        for mois in JOURS_DE_LA_FENETRE:
            _clear_actual(admin, emps[nom]["id"], YEAR, mois)
