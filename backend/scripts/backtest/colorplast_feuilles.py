"""Feuilles de pointage de Colorplast, février à mai 2026, transcrites.

Même règle que janvier et juin (annotée par Gaëlle sur la feuille S03) :
heures = fin − début − 0,5 h de pause quand la journée dépasse 6 h. Quand
Gaëlle a elle-même écrit les heures de chaque jour en marge (S05 à S07 de
février), c'est sa lecture qui est retenue : elle a vu l'original. Prénoms →
salariés : Marion = Gautheron, Michel = Bugny, Anthony = Espinosa, Léo =
Cotte, Aurélien = Demory (à partir du 23/03), Hugo = Fuckar (à partir du
07/04). Girerd (cadre) n'a pas de feuille.

Un jour absent du dictionnaire = pas de pointage (neutre). Un jour à 0,0 =
pointé absent. Les congés, fériés non payés, journées de récupération et
absences déclarées viennent du calendrier du cabinet
(`colorplast_calendrier_cabinet`), les arrêts de la DSN.

Les incertitudes de lecture sont listées dans INCERTITUDES, avec ce qui a été
retenu et pourquoi.
"""

from __future__ import annotations

#: (mois, jour) → heures nettes, par salarié et par mois de la fenêtre.
FEUILLES: dict[int, dict[str, dict[tuple[int, int], float]]] = {
    # ---- fenêtre de février : 26/01 → 22/02, semaines 5 à 8 --------------------------
    2: {
        "BUGNY": {
            (1, 26): 10.0, (1, 27): 10.0, (1, 28): 10.0, (1, 29): 10.5, (1, 30): 5.0,   # S05 : 45,5 (Gaëlle : 45,50)
            (2, 2): 9.5, (2, 3): 11.0, (2, 4): 11.0, (2, 5): 10.0, (2, 6): 7.5,          # S06 : 49 (Gaëlle : 49)
            (2, 9): 9.5, (2, 10): 11.5, (2, 11): 11.5, (2, 12): 10.0, (2, 13): 9.5,      # S07 : 52 (Gaëlle : 52)
            (2, 16): 10.25, (2, 17): 10.75, (2, 18): 11.0, (2, 19): 10.5, (2, 20): 5.0,  # S08 : 47,5 (7h–17h45, 18h15, 18h30, 18h, 12h)
        },
        "ESPINOSA": {
            (1, 26): 9.5, (1, 27): 9.5, (1, 28): 9.5, (1, 29): 8.5, (1, 30): 5.0,       # S05 : 42 (Gaëlle : 42)
            (2, 2): 9.5, (2, 3): 9.5, (2, 4): 9.5, (2, 5): 8.5, (2, 6): 6.0,             # S06 : 43 (Gaëlle : 43)
            (2, 9): 10.0, (2, 10): 9.5, (2, 11): 10.0, (2, 12): 9.5, (2, 13): 6.0,       # S07 : 45 (Gaëlle : 45)
            (2, 16): 9.5, (2, 17): 10.0, (2, 18): 9.5, (2, 19): 10.0, (2, 20): 6.0,      # S08 : 45
        },
        "COTTE": {
            (1, 26): 8.5, (1, 27): 8.5, (1, 28): 8.5, (1, 29): 8.5, (1, 30): 5.0,       # S05 : 39
            (2, 2): 8.5, (2, 3): 8.5, (2, 4): 8.5, (2, 5): 8.5, (2, 6): 5.0,             # S06 : 39
            (2, 9): 8.5, (2, 10): 8.5, (2, 11): 8.5, (2, 12): 8.5, (2, 13): 5.0,         # S07 : 39
            (2, 16): 8.5, (2, 17): 8.5, (2, 18): 8.5,                                    # S08 : 25,5 + congés des 19 et 20
        },
        "GAUTHERON": {
            # S05 : « OK vu avec Lucas », pas de pointage, 39 h cerclées par Gaëlle.
            (2, 2): 8.5, (2, 3): 8.5, (2, 4): 9.0, (2, 5): 8.5, (2, 6): 5.5,             # S06 : 40 (Gaëlle : 40)
            (2, 9): 8.5, (2, 10): 9.0, (2, 11): 8.5, (2, 12): 9.0, (2, 13): 5.5,         # S07 : 40,5 (Gaëlle : 40,50)
            (2, 16): 9.0, (2, 17): 8.5, (2, 18): 8.0, (2, 19): 8.5, (2, 20): 6.0,        # S08 : 40 (voir INCERTITUDES)
        },
    },
    # ---- fenêtre de mars : 23/02 → 22/03, semaines 9 à 12 ---------------------------
    3: {
        "BUGNY": {
            (2, 23): 11.5, (2, 24): 11.0, (2, 25): 10.0, (2, 26): 10.5,                  # S09 : 43, vendredi non pointé
            (3, 2): 10.25, (3, 3): 11.0, (3, 4): 11.0, (3, 5): 11.0, (3, 6): 7.5,        # S10 : 50,75
            (3, 9): 11.0, (3, 10): 11.0, (3, 11): 10.75, (3, 12): 11.5, (3, 13): 5.5,    # S11 : 49,75 (lundi 6h30–18h, vendredi 7h–12h30)
            (3, 16): 11.5, (3, 17): 10.5, (3, 18): 11.0, (3, 19): 11.0, (3, 20): 5.0,    # S12 : 49 (lundi « MECALAC » 7h–19h)
        },
        "ESPINOSA": {
            (2, 23): 9.5, (2, 24): 9.0, (2, 25): 11.0, (2, 26): 9.5, (2, 27): 6.0,       # S09 : 45
            (3, 2): 9.5, (3, 3): 9.5, (3, 4): 9.5, (3, 5): 8.5, (3, 6): 6.0,             # S10 : 43
            (3, 9): 9.0, (3, 10): 9.5, (3, 11): 11.25, (3, 12): 11.0, (3, 13): 6.0,      # S11 : 46,75
            (3, 16): 8.75, (3, 17): 8.75, (3, 18): 10.25, (3, 19): 8.75, (3, 20): 5.0,   # S12 : 41,5 (6H45 les quatre matins, 7H le vendredi)
        },
        "COTTE": {
            (2, 23): 8.5, (2, 24): 8.5,                                                  # S09 : 17 + événement familial du 25 au 27
            (3, 2): 8.5, (3, 3): 8.5, (3, 4): 8.5, (3, 5): 8.5, (3, 6): 5.0,             # S10 : 39
            (3, 9): 8.5, (3, 10): 8.5, (3, 11): 8.5, (3, 12): 8.5, (3, 13): 5.0,         # S11 : 39
            (3, 16): 8.5, (3, 17): 8.5, (3, 18): 8.5, (3, 19): 8.5, (3, 20): 5.0,        # S12 : 39
        },
        "GAUTHERON": {
            (2, 24): 6.5, (2, 25): 8.5, (2, 26): 6.0, (2, 27): 6.0,                      # S09 : 27 + congé du lundi 23 (« C P » sur la feuille)
            (3, 2): 9.25, (3, 3): 9.25, (3, 4): 8.5, (3, 5): 9.0, (3, 6): 5.0,           # S10 : 41 (vendredi : « 11h » seul, lu 6h–11h)
            (3, 9): 8.0, (3, 10): 8.5, (3, 11): 8.5, (3, 12): 8.5, (3, 13): 5.0,         # S11 : 38,5 (débuts raturés 7h→6h, lu 6h)
            # S12 : arrêt maladie à partir du 16/03 (DSN), feuille vide.
        },
    },
    # ---- fenêtre d'avril : 23/03 → 19/04, semaines 13 à 16 ---------------------------
    4: {
        "BUGNY": {
            (3, 23): 11.25, (3, 24): 11.25, (3, 25): 10.25, (3, 26): 11.25, (3, 27): 5.5,  # S13 : 49,5
            (3, 30): 11.0, (3, 31): 11.5, (4, 1): 12.0, (4, 2): 11.0, (4, 3): 11.0,        # S14 : 56,5 (vendredi 7h–18h30, au stylo vert)
            (4, 7): 9.5, (4, 8): 9.5, (4, 9): 9.5, (4, 10): 5.0,                           # S15 : 33,5 + lundi de Pâques
            (4, 13): 9.5, (4, 14): 9.5, (4, 15): 9.5, (4, 16): 9.5, (4, 17): 5.0,          # S16 : 43
        },
        "ESPINOSA": {
            (3, 23): 8.75, (3, 24): 8.75, (3, 25): 10.25, (3, 26): 11.25, (3, 27): 5.0,    # S13 : 44
            (3, 30): 9.5, (3, 31): 8.75, (4, 1): 12.25, (4, 2): 9.75, (4, 3): 5.0,         # S14 : 45,25
            (4, 7): 8.75, (4, 8): 9.75, (4, 9): 9.75, (4, 10): 5.25,                       # S15 : 33,5 + lundi de Pâques
            (4, 13): 8.75, (4, 14): 8.75, (4, 15): 8.75, (4, 16): 8.75, (4, 17): 5.25,     # S16 : 40,25
        },
        "COTTE": {
            (3, 23): 8.5, (3, 24): 8.5, (3, 25): 8.5, (3, 26): 8.5, (3, 27): 5.0,          # S13 : 39
            (3, 30): 8.5, (3, 31): 9.0, (4, 1): 8.5, (4, 2): 8.5, (4, 3): 5.0,             # S14 : 39,5
            (4, 7): 8.5, (4, 8): 8.5, (4, 9): 8.5, (4, 10): 5.0,                           # S15 : 30,5 + lundi de Pâques
            (4, 13): 8.5, (4, 14): 8.5, (4, 15): 8.5, (4, 16): 8.5, (4, 17): 5.0,          # S16 : 39
        },
        "DEMORY": {
            # Entré le 23/03 : absent des feuilles S13 à S15. Du 23 au 31/03, les
            # heures viennent du calendrier du cabinet (jour par jour) ; du 1ᵉʳ au
            # 10/04, rien — jours sans pointage.
            (3, 23): 8.5, (3, 24): 8.5, (3, 25): 3.0, (3, 26): 8.5, (3, 27): 5.0,          # S13 : 33,5 (calendrier du cabinet)
            (3, 30): 8.5, (3, 31): 8.5,                                                    # S14 : 17 (calendrier du cabinet)
            (4, 13): 8.5, (4, 14): 8.5, (4, 15): 8.5, (4, 16): 8.5, (4, 17): 5.0,          # S16 : 39
        },
        "FUCKAR": {
            (4, 7): 8.5, (4, 8): 8.5, (4, 9): 8.5, (4, 10): 5.0,                           # S15 : 30,5, entré le mardi 7
            (4, 13): 8.5, (4, 14): 8.5, (4, 15): 8.5, (4, 16): 8.5, (4, 17): 5.0,          # S16 : 39
        },
        # GAUTHERON : arrêt maladie du 16/03 au 28/04 (DSN), aucune feuille.
    },
    # ---- fenêtre de mai : 20/04 → 24/05, semaines 17 à 21 ------------------------------
    5: {
        "BUGNY": {
            (4, 20): 9.5, (4, 22): 9.5, (4, 23): 8.5,                                      # S17 : 27,5 pointées (mardi vide, vendredi sans fin)
            (4, 27): 9.5, (4, 28): 9.5, (4, 29): 9.5, (4, 30): 9.5,                        # S18 : 38 + 1ᵉʳ mai
            (5, 4): 9.5, (5, 5): 9.5, (5, 6): 9.5, (5, 7): 9.5,                            # S19 : 38 + 8 mai
            (5, 11): 9.5, (5, 12): 9.5, (5, 13): 9.5, (5, 15): 5.0,                        # S20 : 33,5 + Ascension
            (5, 18): 9.5, (5, 19): 9.5, (5, 20): 9.5, (5, 21): 9.5, (5, 22): 5.0,          # S21 : 43
        },
        "ESPINOSA": {
            (4, 20): 5.75, (4, 21): 8.75, (4, 22): 10.75, (4, 23): 9.25, (4, 24): 7.5,     # S17 : 42 (lundi lu 6H45–12H30, voir INCERTITUDES)
            (4, 27): 8.75, (4, 28): 8.75, (4, 29): 12.0, (4, 30): 11.5,                    # S18 : 41 + 1ᵉʳ mai
            (5, 4): 9.5, (5, 5): 9.5, (5, 6): 10.5, (5, 7): 10.5,                          # S19 : 40 + 8 mai
            (5, 11): 9.5, (5, 12): 9.5, (5, 13): 9.5,                                      # S20 : 28,5 + Ascension + vendredi « en récup »
            (5, 18): 9.5, (5, 19): 9.5, (5, 20): 8.5, (5, 21): 10.0, (5, 22): 6.5,         # S21 : 44
        },
        "COTTE": {
            (4, 20): 8.5, (4, 21): 8.5, (4, 22): 8.5, (4, 23): 9.0, (4, 24): 6.5,          # S17 : 41
            (4, 27): 8.5, (4, 28): 8.5, (4, 29): 8.5, (4, 30): 8.5,                        # S18 : 34 + 1ᵉʳ mai
            (5, 4): 8.5, (5, 5): 8.5, (5, 6): 8.5, (5, 7): 8.5,                            # S19 : 34 + 8 mai (mardi 6h30–15h30)
            (5, 11): 8.5, (5, 12): 8.5, (5, 13): 8.5, (5, 15): 5.0,                        # S20 : 30,5 + Ascension
            (5, 18): 8.5, (5, 19): 8.5, (5, 20): 8.5, (5, 21): 8.5, (5, 22): 5.0,          # S21 : 39
        },
        "FUCKAR": {
            (4, 20): 8.5, (4, 21): 9.0, (4, 22): 8.5, (4, 23): 12.0, (4, 24): 5.0,         # S17 : 43
            (4, 27): 8.5, (4, 28): 8.5, (4, 29): 8.5, (4, 30): 8.5,                        # S18 : 34 + 1ᵉʳ mai
            (5, 4): 8.5,                                                                   # S19 : 8,5 + arrêt maladie du 5 au 8 (DSN)
            (5, 11): 8.5, (5, 12): 11.5, (5, 13): 8.0, (5, 15): 4.5,                       # S20 : 32,5 + Ascension (vendredi 7h30–12h)
            (5, 18): 9.5, (5, 19): 9.5, (5, 20): 8.5, (5, 21): 5.0, (5, 22): 6.5,          # S21 : 39 (jeudi 11h–16h, vendredi 7h–14h)
        },
        "DEMORY": {
            (4, 20): 8.5, (4, 21): 8.5, (4, 22): 8.5, (4, 23): 8.5, (4, 24): 5.0,          # S17 : 39 (écrit en marge, hors grille)
            (4, 27): 8.5, (4, 28): 8.5, (4, 29): 8.5, (4, 30): 8.5,                        # S18 : 34 + 1ᵉʳ mai
            (5, 4): 8.5, (5, 5): 9.0, (5, 6): 8.5,                                         # S19 : 26, jeudi 7 vide, + 8 mai
            (5, 11): 8.5, (5, 12): 8.5, (5, 13): 8.5,                                      # S20 : 25,5, + Ascension, vendredi 15 vide
            (5, 18): 8.5, (5, 19): 8.5, (5, 20): 8.5, (5, 21): 8.5, (5, 22): 5.0,          # S21 : 39 (le 22 : « jour AT » au calendrier du cabinet)
        },
        "GAUTHERON": {
            # Reprise le mercredi 29/04 après l'arrêt (DSN : 29/03 → 28/04).
            (4, 29): 8.5, (4, 30): 8.5,                                                    # S18 : 17 + 1ᵉʳ mai
            (5, 4): 8.5, (5, 5): 8.5, (5, 6): 8.5, (5, 7): 8.5,                            # S19 : 34 + 8 mai
            (5, 11): 8.5, (5, 12): 8.5, (5, 13): 8.5,                                      # S20 : 25,5 + Ascension + congé du 15
            (5, 18): 8.5, (5, 19): 8.5, (5, 20): 8.5, (5, 21): 8.5, (5, 22): 5.0,          # S21 : 39 (vendredi 6h–11h)
        },
    },
}

#: Lectures douteuses, et ce qui a été retenu.
INCERTITUDES: list[str] = [
    "Février S05, Espinosa mardi 27/01 : la case FIN se lit « 10H » ; Gaëlle a compté 9,5 h (6H–16H) et sa "
    "somme de 42 h en dépend. Retenu 9,5. Le script de janvier avait lu 4,0 (6h–10h).",
    "Février S06 et S07, Bugny lundi : FIN se lit « 18h » (10,5 h) mais Gaëlle compte 9,5 h les deux fois, "
    "et ses totaux 49 et 52 en dépendent. Retenu 9,5, comme elle.",
    "Mars S09, Gautheron jeudi 26/02 : 6h–12h (6 h) et mardi 24/02 8h30–15h30 (6,5 h) ; le cabinet n'a retenu "
    "que 0,90 h d'absence sur la semaine. Retenu ce que dit la feuille.",
    "Mars S11, Gautheron : les heures de début sont raturées (7h corrigé en 6h) du mardi au vendredi. Retenu 6h.",
    "Mars S12, Espinosa lundi à jeudi : 6H45 ; le cabinet paie 14,75 h à 25 % contre 14,5 lues, soit un "
    "quart d'heure quelque part dans le mois. Retenu la feuille.",
    "Avril S13–S15, Demory : entré le 23/03, il n'apparaît sur les feuilles qu'à partir de S16. Du 23 au "
    "31/03 ses heures sont celles du calendrier du cabinet (50,5 h) ; du 1ᵉʳ au 10/04, rien n'est pointé.",
    "Mai S17, Bugny : mardi 21/04 vide et vendredi 24/04 « 6h30 » sans heure de fin. Les deux jours sont "
    "laissés sans pointage (neutres), ni travail ni absence.",
    "Mai S17, Espinosa lundi 20/04 : fin lue « 2H30 », le premier chiffre pris dans la bordure. Retenu "
    "12H30 (5,75 h) ; 17H30 donnerait 10,25 h et 4,5 h de plus dans la semaine.",
    "Mai S19 et S20, Demory : jeudi 7/05 et vendredi 15/05 vides. Laissés sans pointage. Le calendrier "
    "du cabinet ne dit rien de ces deux jours.",
    "Mai S20 : la feuille porte « S19 » en titre mais couvre bien le 11–15/05 (Ascension le jeudi).",
    "Février S08, Gautheron : mercredi 6h30–15h annoté « (−1h) », vendredi 6h–12h annoté « 45 min » ; "
    "aucun total de Gaëlle. Retenu 8,0 et 6,0 (annotations ignorées), soit 40 h, ce qui rejoint l'heure "
    "sup payée pour cette semaine (3,5 h payées sur le mois = 1 + 1,5 + 1).",
]


# ---------------------------------------------------------------------------
# Fenêtres, règle hebdomadaire et pose au calendrier réel
# ---------------------------------------------------------------------------
import copy  # noqa: E402
from collections import defaultdict  # noqa: E402
from datetime import date  # noqa: E402

from app.core.database import get_supabase_admin_client, supabase  # noqa: E402
from scripts.backtest.colorplast_setup import _clear_actual  # noqa: E402

YEAR = 2026
#: Contrat de 39 h : la 40ᵉ à la 43ᵉ heure de la semaine à 25 %, au-delà à 50 %.
DUREE_CONTRAT, SEUIL_50 = 39.0, 43.0
#: Fenêtre des variables de chaque mois (celle du rejeu).
FENETRES: dict[int, tuple[date, date]] = {
    1: (date(2025, 12, 22), date(2026, 1, 25)),
    2: (date(2026, 1, 26), date(2026, 2, 22)),
    3: (date(2026, 2, 23), date(2026, 3, 22)),
    4: (date(2026, 3, 23), date(2026, 4, 19)),
    5: (date(2026, 4, 20), date(2026, 5, 24)),
    6: (date(2026, 5, 25), date(2026, 6, 21)),
    7: (date(2026, 6, 22), date(2026, 7, 26)),
}
#: Jours fériés 2026 (métropole).
FERIES = {date(2026, 1, 1), date(2026, 4, 6), date(2026, 5, 1), date(2026, 5, 8), date(2026, 5, 14),
          date(2026, 5, 25), date(2026, 7, 14), date(2026, 8, 15), date(2026, 11, 1), date(2026, 11, 11),
          date(2026, 12, 25)}
#: Congés lus sur les feuilles elles-mêmes (« C P » écrit dans la case).
CONGES_DES_FEUILLES: dict[str, set[tuple[int, int]]] = {"GAUTHERON": {(2, 23)}}
#: Congé pour événement familial : le classeur ne marque que le premier jour ;
#: le décès d'un parent ouvre trois jours (L3142-4), et la feuille S09 laisse
#: Cotte sans pointage du 25 au 27.
EVENEMENTS_FAMILIAUX: dict[str, list[tuple[int, int]]] = {"COTTE": [(2, 25), (2, 26), (2, 27)]}


def heures_par_semaine(feuille: dict[tuple[int, int], float]) -> dict[int, float]:
    """Total pointé de chaque semaine ISO (numéro de semaine → heures)."""
    totaux: dict[int, float] = defaultdict(float)
    for (mois, jour), heures in feuille.items():
        totaux[date(YEAR, mois, jour).isocalendar()[1]] += heures
    return {semaine: round(total, 2) for semaine, total in sorted(totaux.items())}


def heures_sup_attendues(feuille: dict[tuple[int, int], float]) -> tuple[float, float]:
    """Ce que la règle hebdomadaire donne sur les seules heures pointées : (à 25 %, à 50 %).

    Les fériés et les congés sont à 0 h prévue dans la base, donc jamais
    assimilés : le compteur d'une semaine est son seul total pointé. C'est ce
    que fait le moteur aujourd'hui ; ce qu'il devrait faire est une question
    ouverte (voir docs/colorplast-juin-2026-ligne-a-ligne.md).
    """
    hs25 = hs50 = 0.0
    for total in heures_par_semaine(feuille).values():
        hs25 += min(max(total - DUREE_CONTRAT, 0.0), SEUIL_50 - DUREE_CONTRAT)
        hs50 += max(total - SEUIL_50, 0.0)
    return round(hs25, 2), round(hs50, 2)


def _mois_de_la_fenetre(mois: int) -> dict[int, set[int]]:
    debut, fin = FENETRES[mois]
    jours: dict[int, set[int]] = defaultdict(set)
    d = debut
    while d <= fin:
        if d.year == YEAR:
            jours[d.month].add(d.day)
        d = date.fromordinal(d.toordinal() + 1)
    return jours


def _schedule(emp_id: str, mois: int) -> dict | None:
    rows = (
        supabase.table("employee_schedules").select("id, planned_calendar, actual_hours")
        .match({"employee_id": emp_id, "year": YEAR, "month": mois}).execute()
    ).data or []
    return rows[0] if rows else None


def regulariser_le_planning(emps: dict, mois: int, evenements) -> None:
    """Le planning de la fenêtre ne porte que ce que disent les sources régulières.

    Les absences que le setup avait recopiées des bulletins (congés, absences
    non rémunérées, événements familiaux) sont remises à l'horaire du jour ;
    les fériés restent des fériés, les arrêts de la DSN ne sont pas touchés.
    Puis sont posés : les congés du classeur du cabinet et des feuilles, les
    événements familiaux. Les absences non justifiées ne se posent pas : elles
    viennent du pointage (une journée à 0 h, une journée courte).
    """
    conges = defaultdict(set)
    quotites = {}
    for ev in evenements:
        if ev.nature == "cp" and isinstance(ev.valeur, (int, float)) and ev.valeur > 0:
            conges[ev.salarie].add((ev.mois, ev.jour))
            quotites[(ev.salarie, ev.mois, ev.jour)] = float(ev.valeur)
    for nom, jours in CONGES_DES_FEUILLES.items():
        conges[nom] |= jours
    for nom, emp in emps.items():
        for mm, jours_fenetre in _mois_de_la_fenetre(mois).items():
            sched = _schedule(emp["id"], mm)
            if not sched:
                continue
            planned = copy.deepcopy(sched.get("planned_calendar") or {})
            cal = planned.get("calendrier_prevu") or []
            heures_semaine: dict[int, float] = {}
            for j in cal:
                if j.get("type") == "travail" and j.get("heures_prevues"):
                    heures_semaine.setdefault(date(YEAR, mm, int(j["jour"])).weekday(), float(j["heures_prevues"]))
            changements = []
            for j in cal:
                jour = int(j["jour"])
                if jour not in jours_fenetre:
                    continue
                d = date(YEAR, mm, jour)
                typ = str(j.get("type") or "")
                if typ.startswith("arret") or j.get("dsn_loader") or d.weekday() >= 5:
                    continue
                if typ in ("conges_payes", "absence_non_remuneree", "evenement_familial"):
                    for cle in ("manuel", "origine", "quotite_absence"):
                        j.pop(cle, None)
                    if d in FERIES:
                        j.update({"type": "ferie", "heures_prevues": 0.0})
                    else:
                        j.update({"type": "travail", "heures_prevues": heures_semaine.get(d.weekday(), 8.5 if d.weekday() < 4 else 5.0)})
                    changements.append(f"{d:%d/%m} remis")
                if (mm, jour) in conges[nom] and d not in FERIES:
                    j.update({"type": "conges_payes", "manuel": True, "origine": "absence"})
                    q = quotites.get((nom, mm, jour), 1.0)
                    if 0 < q < 1:
                        j["quotite_absence"] = q
                    changements.append(f"{d:%d/%m} congé")
                if (mm, jour) in EVENEMENTS_FAMILIAUX.get(nom, []):
                    j.update({"type": "evenement_familial", "manuel": True})
                    changements.append(f"{d:%d/%m} évt familial")
            planned["calendrier_prevu"] = sorted(cal, key=lambda x: int(x["jour"]))
            supabase.table("employee_schedules").update({"planned_calendar": planned}).eq("id", sched["id"]).execute()
            if changements:
                print(f"  {nom:10s} planning {mm:02d} : {', '.join(changements)}")


def poser_les_feuilles(emps: dict, mois: int, feuilles: dict[str, dict[tuple[int, int], float]]) -> None:
    """Écrit les journées pointées de la fenêtre au calendrier réel des deux mois qu'elle couvre.

    Les jours prévus en férié ou en congé sans heure pointée sont recopiés tels
    quels ; une journée pointée sur un férié est écrite en travail. Les heures
    sup posées en saisie par le setup sont ensuite effacées pour tout le monde :
    le moteur doit les retrouver seul.
    """
    for nom, emp in emps.items():
        heures = feuilles.get(nom, {})
        postes = []
        for mm, jours_fenetre in _mois_de_la_fenetre(mois).items():
            sched = _schedule(emp["id"], mm)
            if not sched:
                continue
            par_jour = {int(j["jour"]): j for j in (sched.get("planned_calendar") or {}).get("calendrier_prevu", [])}
            reel = []
            for jour in sorted(par_jour):
                if jour not in jours_fenetre:
                    continue
                prevu = par_jour[jour]
                if (mm, jour) in heures:
                    reel.append({"jour": jour, "type": "travail", "heures_faites": heures[(mm, jour)]})
                elif prevu.get("type") == "ferie":
                    reel.append({"jour": jour, "type": "ferie", "heures_faites": None})
                elif prevu.get("type") == "conges_payes":
                    reel.append({"jour": jour, "type": "conge", "heures_faites": 0.0})
            actual = copy.deepcopy(sched.get("actual_hours") or {})
            actual["periode"] = {"mois": mm, "annee": YEAR}
            actual["calendrier_reel"] = reel
            supabase.table("employee_schedules").update({"actual_hours": actual}).eq("id", sched["id"]).execute()
            postes.append(f"{len([r for r in reel if r['type'] == 'travail'])} j. en {mm:02d}")
        print(f"  {nom:10s} : {', '.join(postes) or 'aucun pointage'}")
        supabase.table("monthly_inputs").delete().match(
            {"employee_id": emp["id"], "year": YEAR, "month": mois}
        ).ilike("name", "%suppl%").execute()


def effacer_les_feuilles(emps: dict, mois: int) -> None:
    admin = get_supabase_admin_client()
    for emp in emps.values():
        for mm in _mois_de_la_fenetre(mois):
            _clear_actual(admin, emp["id"], YEAR, mm)
