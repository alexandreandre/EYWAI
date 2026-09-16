"""Rejeu de Colorplast 2026 sur le TEST, mois après mois, comparé à Quadra.

Le cabinet calcule l'allègement en cumulé : celui d'un mois vaut l'allègement dû
sur tous les mois écoulés moins celui déjà pris. Le cumul voyage de mois en mois
dans `employee_schedules.cumuls`, donc **un mois ne peut être juste que si les
précédents le sont**. Ce script déroule donc les mois dans l'ordre depuis
janvier, en bac à sable dans le temps : l'état des fiches est relevé avant et
remis après, et chaque mois est comparé au bulletin du cabinet.

Janvier vient des feuilles de pointage (`data/colorplast/pointages/2026-01/`,
règle de Gaëlle annotée sur S03 : heures = fin − début − 0,5 h de pause au-delà
de 6 h) ; les mois suivants viennent du setup du backtest, c'est-à-dire des
heures sup que le cabinet a réellement payées. C'est volontaire : on juge le
moteur sur les entrées de Quadra, pas sur notre lecture des feuilles. Ce que les
feuilles disent est une question de saisie, traitée à part (Bugny, 95 h relevées
sur janvier-mars pour 46,5 payées, question Q6 à Gaëlle).

Deux copies en double sont écartées avant de commencer, faute de quoi le moteur
les additionne — voir `_nettoyer_les_doublons_du_cabinet`.

Références : `data/colorplast/bulletins/2026-MM/` et `data/colorplast/dsn/`.
Détail des écarts dans `docs/colorplast-{janvier,fevrier}-2026-ligne-a-ligne.md`.

Exécuté en CI via `script-env-test.yml`. Usage : [--apply] [--jusqu-a N]
"""

from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import get_supabase_admin_client, supabase  # noqa: E402
from app.modules.payslips.application.commands import generate_payslip  # noqa: E402
from app.modules.payslips.application.dto import (  # noqa: E402
    GeneratePayslipInput,
    PayslipBadRequestError,
    PayslipCalendarIncompleteError,
)
from scripts.backtest.colorplast_feuilles_janvier import poser_les_feuilles  # noqa: E402
from scripts.backtest.colorplast_setup import _clear_actual, apply_month  # noqa: E402

COMPANY_ID = "dbe2b9f5-44dd-41bc-a625-36ed33d160f7"  # Colorplast
YEAR = 2026
#: Toutes les fiches que le rejeu touche sur l'année. Chaque mois n'en joue
#: qu'une partie — Demory est embauché le 23/03 — et c'est le tableau de
#: références du mois qui dit lesquelles.
SALARIES = ("BUGNY", "COTTE", "DEMORY", "ESPINOSA", "FUCKAR", "GAUTHERON", "GIRERD")
#: Le SMIC horaire imprimé change en cours d'année : 12,02 € jusqu'en mai,
#: 12,31 € au 1ᵉʳ juin 2026. À ne pas confondre avec le SMIC de RÉFÉRENCE de
#: l'allègement, lui gelé à 12,02 € pour toute l'année (LFSS 2025).
SMIC_HORAIRE = {m: 12.02 for m in range(1, 6)} | {m: 12.31 for m in range(6, 13)}

#: Tolérances par défaut : le centime, sauf le SMIC (au demi-centime) et les
#: lignes où le cabinet est connu pour ne pas être cohérent avec lui-même.
TOLERANCES = {
    "brut": 0.05, "net": 0.05, "pas": 0.05, "net_social": 0.05, "net_hs_exo": 0.05,
    "heures": 0.05, "pss": 0.05, "smic": 0.005, "autres": 0.05,
    "deduction": 0.005, "reduction": 0.05,
}

#: Chiffres relevés sur les bulletins Quadra, mois par mois.
#: `net` = (net à payer avant impôt, impôt à la source).
#: `heures` = (cumul heures, cumul h. sup) de l'encadré, cumulés depuis janvier.
REFERENCES: dict[int, dict] = {
    1: {
        "fenetre": ("2025-12-22", "2026-01-25"),
        # Janvier porte l'incohérence connue du cabinet sur les heures d'une
        # absence : trois valeurs différentes pour Cotte (16,97 imprimé / 16,99
        # pour la déduction / 17,11 pour l'allègement). D'où les tolérances
        # élargies sur les seules lignes concernées — question Q3 à Gaëlle.
        "tolerances": {"net": 0.15, "net_social": 0.15, "net_hs_exo": 1.0,
                       "deduction": 0.15, "reduction": 5.0},
        "brut": {"BUGNY": 3023.40, "COTTE": 2351.89, "ESPINOSA": 3046.68,
                 "GAUTHERON": 2252.28, "GIRERD": 3799.06},
        # Gros acomptes en janvier : le net à payer est ce qui reste après.
        "net": {"BUGNY": (139.02, 63.44), "COTTE": (65.97, 35.52), "ESPINOSA": (74.06, 0.0),
                "GAUTHERON": (54.69, 25.42), "GIRERD": (159.74, 111.81)},
        "net_social": {"BUGNY": 2508.65, "COTTE": 1880.84, "ESPINOSA": 2538.18,
                       "GAUTHERON": 1769.08, "GIRERD": 3149.64},
        "net_hs_exo": {"BUGNY": 645.56, "COTTE": 256.64, "ESPINOSA": 611.08,
                       "GAUTHERON": 245.46, "GIRERD": 413.31},
        "heures": {"BUGNY": (189.50, 37.83), "COTTE": (165.50, 16.97), "ESPINOSA": (185.00, 33.33),
                   "GAUTHERON": (158.00, 16.20), "GIRERD": (169.00, 17.33)},
        # Proratisé en jours calendaires d'absence non rémunérée : Cotte 30/31,
        # Gautheron 29/31.
        "pss": {"BUGNY": 4005.00, "COTTE": 3875.81, "ESPINOSA": 4005.00,
                "GAUTHERON": 3746.61, "GIRERD": 4005.00},
        "autres": {"BUGNY": 53.22, "COTTE": 39.61, "ESPINOSA": 53.63,
                   "GAUTHERON": 40.26, "GIRERD": 89.41},
        "deduction": {"BUGNY": -56.75, "COTTE": -25.49, "ESPINOSA": -50.00,
                      "GAUTHERON": -24.38, "GIRERD": -26.00},
        "reduction": {"BUGNY": -569.91, "COTTE": -609.61, "ESPINOSA": -524.94,
                      "GAUTHERON": -582.21, "GIRERD": -252.64},
    },
    2: {
        "fenetre": ("2026-01-26", "2026-02-22"),
        # Février ne porte aucune absence non rémunérée : tout est au centime,
        # sauf la traîne de janvier sur l'allègement de Gautheron (−0,26).
        "tolerances": {"reduction": 0.30},
        "brut": {"BUGNY": 2634.90, "COTTE": 2398.38, "ESPINOSA": 3104.24,
                 "GAUTHERON": 2455.03, "GIRERD": 3799.06},
        "net": {"BUGNY": (2741.73, 63.51), "COTTE": (1918.04, 36.22), "ESPINOSA": (2491.84, 0.0),
                "GAUTHERON": (1838.78, 27.09), "GIRERD": (3051.51, 111.81)},
        # Le net social exclut le complément de mutuelle famille (98,13 chez
        # Espinosa, Gautheron et Girerd), retenu après lui, mais inclut le
        # transport et le remboursement de notes de frais.
        "net_social": {"BUGNY": 2741.73, "COTTE": 1918.04, "ESPINOSA": 2589.97,
                       "GAUTHERON": 1936.91, "GIRERD": 3149.64},
        "net_hs_exo": {"BUGNY": 283.02, "COTTE": 261.77, "ESPINOSA": 664.80,
                       "GAUTHERON": 314.63, "GIRERD": 413.31},
        "heures": {"BUGNY": (358.50, 55.16), "COTTE": (334.50, 34.30), "ESPINOSA": (373.00, 69.66),
                   "GAUTHERON": (330.50, 37.03), "GIRERD": (338.00, 34.66)},
        "pss": {nom: 4005.00 for nom in ("BUGNY", "COTTE", "ESPINOSA", "GAUTHERON", "GIRERD")},
        "autres": {"BUGNY": 46.68, "COTTE": 40.37, "ESPINOSA": 54.58,
                   "GAUTHERON": 43.66, "GIRERD": 89.41},
        "deduction": {"BUGNY": -26.00, "COTTE": -26.00, "ESPINOSA": -54.50,
                      "GAUTHERON": -31.25, "GIRERD": -26.00},
        "reduction": {"BUGNY": -529.50, "COTTE": -622.61, "ESPINOSA": -531.17,
                      "GAUTHERON": -632.28, "GIRERD": -252.63},
    },
    3: {
        "fenetre": ("2026-02-23", "2026-03-22"),
        # Mars apporte trois mécanismes nouveaux d'un coup : l'arrêt maladie de
        # Gautheron (16→28/03, dont 3 jours de maintien de salaire, et des
        # heures sup dont une part perd l'exonération), le congé pour événement
        # familial de Cotte (25→27/02, payé mais qui sort les heures du compteur
        # et proratise le plafond) et l'embauche de Demory le 23/03.
        # Gautheron est imprimée mais ne fait pas échouer le rejeu : la
        # question du maintien de salaire est ouverte, et son bulletin en
        # dépend de bout en bout. Le cabinet lui verse 310,78 € — 3 journées
        # entières — puis plus rien, ni en mars ni en avril où elle tombe à
        # 20,20 € de brut pour un mois d'arrêt complet. Avec plus de quatre ans
        # d'ancienneté, la loi lui garantit 90 % de son salaire pendant 30
        # jours : notre moteur calcule ce plancher et refuse délibérément de
        # descendre en dessous (`conflit_convention`). Le seul montage qui
        # rendrait le bulletin du cabinet régulier est une prise en charge par
        # la prévoyance GAN, versée directement à la salariée et donc absente
        # du bulletin. Question posée à Gaëlle : forcer le moteur à 310,78 €
        # graverait une sous-paie possible dans les sept sociétés.
        "en_attente": {
            "GAUTHERON": "maintien de salaire de l'arrêt du 16 au 28/03 — "
                         "question ouverte, voir docs/colorplast-mars-2026-ligne-a-ligne.md",
        },
        # Écarts avec le cabinet que nous ne reproduisons pas, et pourquoi.
        #
        # Cotte, congé pour événement familial : sa rémunération étant
        # intégralement maintenue, ni le plafond ni le compteur d'heures ne se
        # réduisent. Le cabinet proratise pourtant le plafond de 3 jours — sans
        # aucun effet financier, le brut (2 398,38) restant sous le plafond dans
        # les deux cas — et sort les heures du compteur, alors qu'il garde
        # celles du congé payé de Léo en février. Nous restons cohérents.
        #
        # Les deux écarts d'allègement ne sont pas tranchés : Cotte relève de la
        # même incohérence que janvier (question Q3, le cabinet compte une
        # fraction d'heure de plus ou de moins quand il y a une absence) et la
        # règle du mois d'entrée de Demory n'est pas identifiée — notre formule
        # tourne pourtant sur les bonnes heures, 50,50 comme lui.
        "ecarts_documentes": {
            "COTTE": {"pss": 429.11, "cumul_heures": 23.40, "cumul_hs": 2.40,
                      "reduction": -5.71},
            "DEMORY": {"reduction": -29.70},
        },
        "brut": {"BUGNY": 3124.90, "COTTE": 2398.38, "DEMORY": 625.25,
                 "ESPINOSA": 3139.74, "GAUTHERON": 1609.96, "GIRERD": 3799.06},
        "net": {"BUGNY": (2751.38, 63.42), "COTTE": (1918.04, 36.22), "DEMORY": (496.93, 0.0),
                "ESPINOSA": (2523.79, 0.0), "GAUTHERON": (1157.34, 18.02), "GIRERD": (3051.51, 111.81)},
        "net_social": {"BUGNY": 2751.38, "COTTE": 1918.04, "DEMORY": 496.93,
                       "ESPINOSA": 2621.92, "GAUTHERON": 1255.47, "GIRERD": 3149.64},
        "net_hs_exo": {"BUGNY": 740.28, "COTTE": 261.77, "DEMORY": 42.69,
                       "ESPINOSA": 697.92, "GAUTHERON": 175.97, "GIRERD": 413.31},
        "heures": {"BUGNY": (553.50, 98.49), "COTTE": (480.10, 49.23), "DEMORY": (50.50, 3.00),
                   "ESPINOSA": (562.50, 107.49), "GAUTHERON": (420.50, 46.26), "GIRERD": (507.00, 51.99)},
        # Proratisé chez les trois salariés dont le mois n'est pas entier : Cotte
        # ses 3 jours d'événement familial, Gautheron son arrêt, Demory son
        # embauche le 23.
        "pss": {"BUGNY": 4005.00, "COTTE": 3575.89, "DEMORY": 1162.74,
                "ESPINOSA": 4005.00, "GAUTHERON": 2957.61, "GIRERD": 4005.00},
        # Demory est en CDD : 2,646 % au lieu de 1,646 %, le point d'écart étant
        # la contribution au financement du CPF des titulaires de CDD.
        "autres": {"BUGNY": 54.93, "COTTE": 40.37, "DEMORY": 16.78,
                   "ESPINOSA": 55.19, "GAUTHERON": 29.44, "GIRERD": 89.41},
        # Chez Gautheron la base n'est pas son compteur d'heures sup (9,23) mais
        # 11,65 h : le bulletin porte la mention « 11,65 H.sup exo / 5,68 H
        # n.exo » — seules les heures sup rattachées à la part non maintenue de
        # l'arrêt perdent l'exonération. Chez Cotte c'est l'inverse : 17,33 h de
        # base alors que son compteur n'affiche que 14,93, parce que son absence
        # est payée.
        "deduction": {"BUGNY": -65.00, "COTTE": -26.00, "DEMORY": -4.50,
                      "ESPINOSA": -56.75, "GAUTHERON": -17.48, "GIRERD": -26.00},
        "reduction": {"BUGNY": -581.69, "COTTE": -617.14, "DEMORY": -201.39,
                      "ESPINOSA": -531.66, "GAUTHERON": -419.16, "GIRERD": -252.64},
    },
    4: {
        "fenetre": ("2026-03-23", "2026-04-19"),
        # Avril apporte encore trois choses : l'embauche de Fuckar le 07/04 avec
        # sa retenue d'entrée, un jour férié non payé chez Demory (moins de trois
        # mois d'ancienneté), et la part patronale de mutuelle réintégrée au net
        # imposable à partir de ce mois — le PAS de Girerd passe de 111,81 à
        # 113,05. Gautheron est en arrêt tout le mois : son bulletin est négatif
        # (−114,82 à payer) et son allègement se retourne en remboursement.
        "en_attente": {
            "GAUTHERON": "arrêt maladie du 29/03 au 28/04 — même question ouverte qu'en mars",
        },
        # Écarts avec le cabinet que nous ne reproduisons pas.
        #
        # Cotte traîne son congé pour événement familial de mars : le cabinet en
        # a sorti les heures du compteur, nous les gardons (voir mars).
        #
        # Fuckar, mois d'embauche : le cabinet garde ses 17,33 h structurelles
        # entières au compteur (22,33 avec ses heures sup) tout en n'en exonérant
        # que 14,28 — son bulletin porte « 14,28 H.sup exo / 3,05 H n.exo ». Les
        # 3,05 h sont celles rattachées aux 30,50 h non travaillées avant son
        # embauche : nous les sortons du compteur comme du SMIC de référence,
        # puisqu'elles ne sont pas payées. D'où les 42,38 d'allègement, dont
        # environ 34 viennent de ces heures et 8 de l'écart habituel entre les
        # heures que le cabinet imprime et celles qu'il calcule.
        #
        # Les deux petits restes d'allègement (Cotte, Demory) sont de la même
        # famille que les précédents.
        "ecarts_documentes": {
            "COTTE": {"cumul_heures": 23.40, "cumul_hs": 2.40, "reduction": -0.51},
            "DEMORY": {"reduction": -0.42},
            "FUCKAR": {"cumul_heures": -3.05, "cumul_hs": -3.05, "reduction": 42.38},
        },
        "brut": {"BUGNY": 2949.90, "COTTE": 2430.75, "DEMORY": 2017.05, "ESPINOSA": 3156.05,
                 "FUCKAR": 1818.80, "GAUTHERON": 20.20, "GIRERD": 3799.06},
        "net": {"BUGNY": (3415.42, 64.45), "COTTE": (1947.18, 36.22), "DEMORY": (1614.89, 0.0),
                "ESPINOSA": (2538.45, 0.0), "FUCKAR": (1463.72, 0.0),
                "GAUTHERON": (-114.82, 0.29), "GIRERD": (3051.48, 113.05)},
        "net_social": {"BUGNY": 3415.42, "COTTE": 1947.18, "DEMORY": 1614.89, "ESPINOSA": 2636.57,
                       "FUCKAR": 1463.72, "GAUTHERON": -16.70, "GIRERD": 3150.85},
        "net_hs_exo": {"BUGNY": 576.97, "COTTE": 291.99, "DEMORY": 235.24, "ESPINOSA": 713.13,
                       "FUCKAR": 274.38, "GAUTHERON": 0.00, "GIRERD": 413.31},
        "heures": {"BUGNY": (740.50, 133.82), "COTTE": (651.10, 68.56), "DEMORY": (211.70, 19.53),
                   "ESPINOSA": (753.25, 146.57), "FUCKAR": (143.50, 22.33),
                   "GAUTHERON": (417.90, 46.26), "GIRERD": (676.00, 69.32)},
        # Demory perd un jour sur son férié non payé (29/30), Fuckar entre le 07
        # (24/30). Gautheron garde le plafond entier malgré son arrêt.
        "pss": {"BUGNY": 4005.00, "COTTE": 4005.00, "DEMORY": 3871.50, "ESPINOSA": 4005.00,
                "FUCKAR": 3204.00, "GAUTHERON": 4005.00, "GIRERD": 4005.00},
        "autres": {"BUGNY": 51.98, "COTTE": 40.91, "DEMORY": 54.12, "ESPINOSA": 55.46,
                   "FUCKAR": 48.81, "GAUTHERON": 2.68, "GIRERD": 85.28},
        "deduction": {"BUGNY": -53.00, "COTTE": -29.00, "DEMORY": -24.80, "ESPINOSA": -58.62,
                      "FUCKAR": -28.92, "GAUTHERON": 0.42, "GIRERD": -26.00},
        # Gautheron : allègement positif, le cabinet rend ce qu'il avait accordé.
        "reduction": {"BUGNY": -574.00, "COTTE": -627.87, "DEMORY": -725.53, "ESPINOSA": -536.88,
                      "FUCKAR": -642.04, "GAUTHERON": 35.34, "GIRERD": -252.64},
    },
    5: {
        "fenetre": ("2026-04-20", "2026-05-24"),
        # Mai est le mois le plus dense : augmentation générale au 01/05,
        # versement de la participation 2025 (avec des acomptes déjà versés à
        # déduire), journée de solidarité le 25 — travaillée par Bugny et Cotte,
        # posée en congé par les trois autres —, fériés non payés du 8 et du 14
        # pour les deux derniers embauchés, arrêt maladie de Fuckar et accident
        # du travail de Demory. Marion reste en attente : ses cumuls dépendent
        # de son arrêt d'avril, toujours suspendu à la question du maintien.
        #
        # Deux anciens salariés, Chaleyssin et Da Silva Car, reçoivent un
        # bulletin sans salaire pour leur seule part de participation (11,04 et
        # 221,81). Ils ne sont pas dans le périmètre du rejeu.
        "en_attente": {
            "GAUTHERON": "cumuls hérités de son arrêt d'avril — question du maintien toujours ouverte",
        },
        # Écarts avec le cabinet que nous ne reproduisons pas.
        #
        # Cotte traîne toujours son congé pour événement familial de mars.
        # Fuckar traîne son mois d'embauche d'avril, et ses heures d'arrêt
        # maladie : le cabinet les garde au compteur, nous les en sortons.
        #
        # Fuckar garde le seul reste de son mois d'embauche : le cabinet laisse
        # à son compteur les 3,05 h structurelles rattachées aux heures d'avant
        # son arrivée, que nous en sortons (voir avril).
        # Demory et Fuckar gardent un reste d'allègement de 0,09 et 0,47 : même
        # famille que celui de Cotte et que ceux de janvier, le cabinet compte
        # une fraction d'heure autrement que nous dès qu'il y a une absence
        # (question 1). Les compteurs et le plafond, eux, sont exacts.
        "ecarts_documentes": {
            "COTTE": {"cumul_heures": 23.40, "cumul_hs": 2.40, "reduction": 1.18},
            "DEMORY": {"reduction": 0.09},
            "FUCKAR": {"cumul_heures": -3.05, "cumul_hs": -3.05, "reduction": 0.47},
        },
        "brut": {"BUGNY": 2952.34, "COTTE": 2444.33, "DEMORY": 1529.05, "ESPINOSA": 2990.19,
                 "FUCKAR": 1664.78, "GAUTHERON": 2432.78, "GIRERD": 3855.98},
        "net": {"BUGNY": (5479.53, 190.41), "COTTE": (3867.27, 100.04), "DEMORY": (1224.20, 0.0),
                "ESPINOSA": (4860.09, 0.0), "FUCKAR": (1336.64, 0.0),
                "GAUTHERON": (2977.56, 67.22), "GIRERD": (3096.69, 114.75)},
        "net_social": {"BUGNY": 5479.53, "COTTE": 3867.27, "DEMORY": 1224.20, "ESPINOSA": 4958.21,
                       "FUCKAR": 1336.64, "GAUTHERON": 3190.79, "GIRERD": 3711.97},
        "net_hs_exo": {"BUGNY": 538.53, "COTTE": 267.00, "DEMORY": 178.31, "ESPINOSA": 513.72,
                       "FUCKAR": 225.28, "GAUTHERON": 265.69, "GIRERD": 419.51},
        "heures": {"BUGNY": (924.50, 166.15), "COTTE": (820.10, 85.89), "DEMORY": (333.90, 32.06),
                   "ESPINOSA": (931.75, 173.40), "FUCKAR": (276.00, 38.16),
                   "GAUTHERON": (586.90, 63.59), "GIRERD": (845.00, 86.65)},
        "pss": {"BUGNY": 4005.00, "COTTE": 4005.00, "DEMORY": 2842.26, "ESPINOSA": 4005.00,
                "FUCKAR": 3359.03, "GAUTHERON": 4005.00, "GIRERD": 4005.00},
        "autres": {"BUGNY": 52.04, "COTTE": 41.13, "DEMORY": 41.03, "ESPINOSA": 52.67,
                   "FUCKAR": 44.67, "GAUTHERON": 43.28, "GIRERD": 86.53},
        "deduction": {"BUGNY": -48.50, "COTTE": -26.00, "DEMORY": -18.80, "ESPINOSA": -40.25,
                      "FUCKAR": -23.75, "GAUTHERON": -26.00, "GIRERD": -26.00},
        "reduction": {"BUGNY": -546.88, "COTTE": -603.25, "DEMORY": -550.16, "ESPINOSA": -490.36,
                      "FUCKAR": -592.89, "GAUTHERON": -608.28, "GIRERD": -244.99},
    },
    6: {
        # Fenêtre non confirmée sur les pointages : le détail des heures sup que
        # le cabinet fournit pour juin
        # (`data/colorplast/variables/2026-06/detail-heures-sup-06-2026-colorplast.xlsx`)
        # ne reproduit ni les heures payées en juin ni celles de juillet — il
        # donne 10 h à 25 % et 3,5 h à 50 % pour Bugny, qui en reçoit 14 et 7.
        # La fenêtre retenue est la suite logique de mai : semaines ISO entières
        # à partir du lendemain, 25/05 au 21/06.
        "fenetre": ("2026-05-25", "2026-06-21"),
        # Juin apporte deux choses : la revalorisation du SMIC imprimé (12,02 →
        # 12,31 au 01/06 ; le SMIC de référence de l'allègement reste gelé à
        # 12,02) et l'augmentation de Demory et Fuckar, qui passent à 1 867,06.
        #
        # Deux absences d'une journée, toutes deux non payées et toutes deux
        # réduisant le plafond d'un trentième (3 871,50) : Demory le 08/06 et
        # Gautheron le 10/06. Le cabinet les traite pourtant différemment —
        # 8,50 h déduites pour l'un (7,63 + 0,87), 7,80 pour l'autre (7,00 +
        # 0,80) — alors que sa propre feuille d'heures porte 8,50 pour les deux.
        # On pose ce qu'il a payé.
        "en_attente": {
            "GAUTHERON": "cumuls hérités de son arrêt d'avril — question du maintien toujours ouverte",
        },
        # Traînes connues : le congé pour événement familial de Cotte (mars) et
        # les heures d'avant l'embauche de Fuckar (avril).
        #
        # L'allègement de juin est le premier écart sérieux de la série : 18 à
        # 44 € sur cinq salariés, là où les mois précédents tenaient au centime
        # ou à l'euro. La cause est identifiée mais pas tranchée — le cabinet
        # n'applique pas la même référence à tout le monde. En remontant sa
        # formule sur le cumul de janvier à juin :
        #
        #   Bugny  : reproduit au centime par le SMIC de référence GELÉ (12,02),
        #            celui de la configuration et de nos cinq premiers mois ;
        #   Girerd : reproduit à 0,25 € par un SMIC REVALORISÉ (12,31) appliqué
        #            aux seules heures de juin ; Espinosa à 0,74 € ;
        #   Cotte, Fuckar : revalorisé, à 4,50 € près ;
        #   Demory : ni l'un ni l'autre.
        #
        # Le gel est la règle que nous appliquons (LFSS 2025) et il a tenu de
        # janvier à mai. Juin est le premier mois qui pouvait départager les
        # deux, puisque le SMIC n'avait pas bougé avant. On ne change pas le
        # moteur sur une observation qui se contredit d'un bulletin à l'autre :
        # c'est la question 1, désormais chiffrée.
        "ecarts_documentes": {
            "COTTE": {"cumul_heures": 23.40, "cumul_hs": 2.40, "reduction": 38.33},
            "DEMORY": {"reduction": 43.66},
            "ESPINOSA": {"reduction": 35.51},
            "FUCKAR": {"cumul_heures": -3.05, "cumul_hs": -3.05, "reduction": -1.90},
            "GIRERD": {"reduction": 18.32},
        },
        "brut": {"BUGNY": 3084.43, "COTTE": 2444.33, "DEMORY": 2026.41, "ESPINOSA": 3256.34,
                 "FUCKAR": 2450.68, "GAUTHERON": 2327.64, "GIRERD": 3855.98},
        "net": {"BUGNY": (2889.30, 65.64), "COTTE": (1954.81, 36.91), "DEMORY": (1622.42, 0.0),
                "ESPINOSA": (2623.27, 0.0), "FUCKAR": (1970.83, 0.0),
                "GAUTHERON": (1697.87, 26.76), "GIRERD": (3096.69, 114.75)},
        "net_social": {"BUGNY": 2889.30, "COTTE": 1954.81, "DEMORY": 1622.42,
                       "ESPINOSA": 2721.39, "FUCKAR": 1970.83, "GAUTHERON": 1829.37,
                       "GIRERD": 3194.81},
        "net_hs_exo": {"BUGNY": 661.80, "COTTE": 267.00, "DEMORY": 236.36, "ESPINOSA": 762.10,
                       "FUCKAR": 357.98, "GAUTHERON": 253.88, "GIRERD": 419.51},
        "heures": {"BUGNY": (1114.50, 204.48), "COTTE": (989.10, 103.22), "DEMORY": (494.40, 48.52),
                   "ESPINOSA": (1123.75, 213.73), "FUCKAR": (452.00, 62.49),
                   "GAUTHERON": (748.10, 80.12), "GIRERD": (1014.00, 103.98)},
        "pss": {"BUGNY": 4005.00, "COTTE": 4005.00, "DEMORY": 3871.50, "ESPINOSA": 4005.00,
                "FUCKAR": 4005.00, "GAUTHERON": 3871.50, "GIRERD": 4005.00},
        "autres": {"BUGNY": 54.25, "COTTE": 41.13, "DEMORY": 54.37, "ESPINOSA": 57.15,
                   "FUCKAR": 65.76, "GAUTHERON": 41.50, "GIRERD": 86.53},
        "deduction": {"BUGNY": -57.50, "COTTE": -26.00, "DEMORY": -24.69, "ESPINOSA": -60.50,
                      "FUCKAR": -36.50, "GAUTHERON": -24.84, "GIRERD": -26.00},
        "reduction": {"BUGNY": -552.97, "COTTE": -642.15, "DEMORY": -756.59, "ESPINOSA": -551.62,
                      "FUCKAR": -662.25, "GAUTHERON": -617.82, "GIRERD": -263.27},
    },
    7: {
        # Fenêtre dans la continuité de juin, en semaines ISO entières.
        "fenetre": ("2026-06-22", "2026-07-26"),
        # Juillet apporte le morceau le plus lourd de la série : Demory sort le
        # 24/07 en fin de CDD. Son bulletin porte une indemnité de précarité
        # (797,04), une indemnité compensatrice de congés payés (940,23) et un
        # arbitrage de congés (98,48) — trois mécanismes jamais éprouvés ici.
        # Son allègement se retourne d'ailleurs en remboursement (+163,99).
        #
        # Fuckar et Gautheron ont des absences non payées au jour près, prises
        # sur leurs bulletins : le détail n'existe nulle part ailleurs, les
        # feuilles de pointage s'arrêtant à la semaine 25.
        "en_attente": {
            "GAUTHERON": "cumuls hérités de son arrêt d'avril — question du maintien toujours ouverte",
        },
        "ecarts_documentes": {
            "COTTE": {"cumul_heures": 23.40, "cumul_hs": 2.40},
            "FUCKAR": {"cumul_heures": -3.05, "cumul_hs": -3.05},
        },
        "brut": {"BUGNY": 3162.97, "COTTE": 2576.41, "DEMORY": 3509.91, "ESPINOSA": 3191.76,
                 "FUCKAR": 1906.45, "GAUTHERON": 2089.06, "GIRERD": 3855.98},
        "net": {"BUGNY": (3143.84, 65.63), "COTTE": (2173.64, 36.90), "DEMORY": (2785.59, 0.0),
                "ESPINOSA": (2665.17, 0.0), "FUCKAR": (1526.35, 0.0),
                "GAUTHERON": (1593.88, 24.02), "GIRERD": (3195.50, 114.76)},
        "net_social": {"BUGNY": 3143.84, "COTTE": 2173.64, "DEMORY": 2785.59,
                       "ESPINOSA": 2763.29, "FUCKAR": 1526.35, "GAUTHERON": 1738.49,
                       "GIRERD": 3293.62},
        "net_hs_exo": {"BUGNY": 735.09, "COTTE": 390.26, "DEMORY": 206.78, "ESPINOSA": 701.83,
                       "FUCKAR": 222.29, "GAUTHERON": 227.20, "GIRERD": 419.51},
        "heures": {"BUGNY": (1309.00, 247.31), "COTTE": (1166.10, 128.55),
                   "DEMORY": (634.80, 62.92), "ESPINOSA": (1313.00, 251.31),
                   "FUCKAR": (603.00, 77.97), "GAUTHERON": (891.60, 94.84),
                   "GIRERD": (1183.00, 121.31)},
        # Demory 24/31 (sortie), Fuckar 28/31, Gautheron 26/31.
        "pss": {"BUGNY": 4005.00, "COTTE": 4005.00, "DEMORY": 3100.65, "ESPINOSA": 4005.00,
                "FUCKAR": 3617.42, "GAUTHERON": 3359.03, "GIRERD": 4005.00},
        "autres": {"BUGNY": 55.59, "COTTE": 43.37, "DEMORY": 94.18, "ESPINOSA": 56.06,
                   "FUCKAR": 51.17, "GAUTHERON": 37.51, "GIRERD": 90.70},
        "deduction": {"BUGNY": -64.25, "COTTE": -38.00, "DEMORY": -21.60, "ESPINOSA": -56.37,
                      "FUCKAR": -23.22, "GAUTHERON": -22.23, "GIRERD": -26.00},
        # Demory : allègement positif, le cabinet rend ce qu'il avait accordé.
        "reduction": {"BUGNY": -531.92, "COTTE": -582.35, "DEMORY": 163.99, "ESPINOSA": -482.88,
                      "FUCKAR": -669.08, "GAUTHERON": -473.41, "GIRERD": -230.05},
    },
}


def _salaries_du_mois(mois: int) -> tuple[str, ...]:
    """Les salariés que le cabinet a payés ce mois-là."""
    return tuple(sorted(REFERENCES[mois]["brut"]))


def _tolerance(mois: int, cle: str) -> float:
    return REFERENCES[mois].get("tolerances", {}).get(cle, TOLERANCES[cle])


def _generer(employee_id: str, mois: int):
    def _run(force: bool):
        return generate_payslip(
            GeneratePayslipInput(
                employee_id=employee_id, year=YEAR, month=mois,
                force_calendrier_incomplet=force,
                requested_by_name="script colorplast_rejeu_test",
            )
        )
    try:
        return _run(False)
    except PayslipCalendarIncompleteError:
        return _run(True)


def _bulletin(employee_id: str, mois: int) -> dict:
    return (
        supabase.table("payslips").select("payslip_data")
        .match({"employee_id": employee_id, "year": YEAR, "month": mois}).single().execute()
    ).data["payslip_data"]


def _snapshot(ids: list[str]) -> tuple[dict, list]:
    emps = supabase.table("employees").select("*").in_("id", ids).execute().data or []
    hist = supabase.table("salary_history").select("*").in_("employee_id", ids).execute().data or []
    return {e["id"]: e for e in emps}, hist


def _restaurer(emp_avant: dict, hist_avant: list) -> None:
    ids = list(emp_avant)
    apres = {e["id"]: e for e in (supabase.table("employees").select("*").in_("id", ids).execute().data or [])}
    for emp_id, avant in emp_avant.items():
        diff = {k: v for k, v in avant.items() if k != "updated_at" and apres.get(emp_id, {}).get(k) != v}
        if diff:
            supabase.table("employees").update(diff).eq("id", emp_id).execute()
            print(f"  fiche {avant.get('last_name')} : {sorted(diff)} remis")
    ids_avant = {h["id"] for h in hist_avant}
    hist_apres = supabase.table("salary_history").select("id").in_("employee_id", ids).execute().data or []
    retirees = [h for h in hist_apres if h["id"] not in ids_avant]
    for h in retirees:
        supabase.table("salary_history").delete().eq("id", h["id"]).execute()
    for h in hist_avant:
        supabase.table("salary_history").upsert(h).execute()
    print(f"  historique de salaire : {len(hist_avant)} ligne(s) remise(s), {len(retirees)} retirée(s)")


def _nettoyer_les_doublons_du_cabinet(emps: dict, mois_joues: list[int]) -> None:
    """Retire les copies que la base de test porte en double du cabinet.

    Deux chargements coexistent — le setup du backtest et un import DSN — et là
    où ils se recouvrent le moteur additionne au lieu de choisir.

    1. Les heures sup d'un mois existent deux fois (février : Espinosa 15 et 4
       de chaque côté, Gautheron 3,5), donc payées en double. Elles sont
       effacées ici, le setup repose ensuite les siennes.
    2. Les absences importées de la DSN sont datées **en fin de mois** au lieu
       de leur vraie date : Cotte le 30/01 quand son bulletin Quadra dit le 21,
       Gautheron les 29 et 30/01 quand il dit les 13 et 14. Comme la fenêtre
       d'un mois s'arrête avant la fin du mois civil, ces copies mal datées ne
       pèsent pas sur leur propre mois — elles tombent dans la fenêtre du mois
       suivant et y créent des absences qui n'ont jamais eu lieu. Les vraies
       dates sont posées par le setup ; les jours concernés sont remis à
       l'horaire normal de leur jour de semaine.

    Le chargeur date en revanche correctement les arrêts maladie, qui portent
    leurs dates dans la DSN : ils ne sont pas touchés.
    """
    admin = get_supabase_admin_client()
    for mois in mois_joues:
        fin_fenetre = date.fromisoformat(REFERENCES[mois]["fenetre"][1])
        for nom in _salaries_du_mois(mois):
            emp_id = emps[nom]["id"]
            admin.table("monthly_inputs").delete().match(
                {"employee_id": emp_id, "year": YEAR, "month": mois}
            ).ilike("name", "%suppl%").execute()
            # 3. Le complément de mutuelle famille est porté par la fiche depuis
            #    le 25/08 ; une ligne de régularisation saisie en plus le retire
            #    une seconde fois (Espinosa et Girerd, mai : −98,13 de trop sur
            #    le net à payer).
            admin.table("monthly_inputs").delete().match(
                {"employee_id": emp_id, "year": YEAR, "month": mois}
            ).ilike("name", "%mutuelle famille%").execute()

            sched = (
                admin.table("employee_schedules").select("id, planned_calendar")
                .match({"employee_id": emp_id, "year": YEAR, "month": mois})
                .maybe_single().execute()
            )
            if not sched or not sched.data:
                continue
            planned = copy.deepcopy(sched.data.get("planned_calendar") or {})
            jours = planned.get("calendrier_prevu") or []
            heures_du_jour_de_semaine: dict[int, float] = {}
            for j in jours:
                if j.get("type") == "travail" and j.get("heures_prevues"):
                    heures_du_jour_de_semaine.setdefault(
                        date(YEAR, mois, int(j["jour"])).weekday(), j["heures_prevues"]
                    )
            remis = []
            for j in jours:
                jour = date(YEAR, mois, int(j["jour"]))
                if not j.get("dsn_loader") or jour <= fin_fenetre or j.get("type") == "travail":
                    continue
                if j.get("type", "").startswith("arret"):
                    continue
                heures = heures_du_jour_de_semaine.get(jour.weekday())
                if heures is None:
                    continue
                j.update({"type": "travail", "heures_prevues": heures, "manuel": False})
                j.pop("dsn_loader", None)
                remis.append(f"{jour:%d/%m}={heures}")
            # 4. Les jours d'arrêt importés de la DSN n'ont ni nature ni bornes.
            #    Sans elles le moteur les ignore pour le maintien de salaire, et
            #    n'en produit aucun (Gautheron, mars : le cabinet maintient 3
            #    jours pour 310,78 €). Le chargeur les écrit depuis le 15/09 ;
            #    ceux déjà posés sont complétés ici.
            jours_arret = sorted(
                int(j["jour"]) for j in jours
                if str(j.get("type", "")).startswith("arret") and j.get("dsn_loader")
            )
            if jours_arret and any(
                not j.get("arret_type") or not j.get("maintien_base_ouvree")
                for j in jours
                if str(j.get("type", "")).startswith("arret")
            ):
                debut = f"{YEAR:04d}-{mois:02d}-{jours_arret[0]:02d}"
                fin = f"{YEAR:04d}-{mois:02d}-{jours_arret[-1]:02d}"
                for j in jours:
                    if not str(j.get("type", "")).startswith("arret"):
                        continue
                    j.setdefault("origine", "absence")
                    j["arret_type"] = "maladie"
                    j["date_debut_arret_reel"] = debut
                    j["date_fin_arret_reel"] = fin
                    j["subrogation_active"] = False
                    j["maintien_base_ouvree"] = True
                remis.append(f"arrêt {jours_arret[0]}→{jours_arret[-1]} qualifié")
            if remis:
                admin.table("employee_schedules").update(
                    {"planned_calendar": planned}
                ).eq("id", sched.data["id"]).execute()
                print(f"  {nom:10s} {mois:02d}/{YEAR} : {', '.join(remis)}")


def _remettre_a_zero_le_cumul_d_entree(emps: dict, mois: int) -> None:
    """Efface le cumul du mois précédent pour qui débute ce mois-ci.

    Un salarié qui apparaît dans les références d'un mois sans figurer dans
    celles du mois d'avant vient d'être embauché : son compteur doit partir de
    zéro. La base de test porte pourtant des bulletins fantômes antérieurs à
    l'embauche — Demory, arrivé le 23/03, y traîne 492,67 h et 1 056,21 € de
    cumul —, et le moteur repart de ce maillon pour l'allègement comme pour les
    compteurs. Vider la colonne suffit : le générateur retombe alors sur son
    cumul de départ à zéro.
    """
    if mois <= min(REFERENCES):
        return
    precedent = max(m for m in REFERENCES if m < mois)
    arrivants = set(_salaries_du_mois(mois)) - set(_salaries_du_mois(precedent))
    if not arrivants:
        return
    admin = get_supabase_admin_client()
    mois_avant, annee_avant = (mois - 1, YEAR) if mois > 1 else (12, YEAR - 1)
    for nom in sorted(arrivants):
        admin.table("employee_schedules").update({"cumuls": None}).match(
            {"employee_id": emps[nom]["id"], "year": annee_avant, "month": mois_avant}
        ).execute()
        print(f"  {nom:10s} : compteur d'entrée remis à zéro ({mois_avant:02d}/{annee_avant})")

def _controler(nom: str, mois: int, data: dict, res) -> int:
    ref = REFERENCES[mois]
    rc = 0
    # Salarié dont le bulletin est comparé et imprimé, mais ne fait pas échouer
    # le rejeu : une question de fond est ouverte, et figer des écarts en
    # attendant la réponse reviendrait à graver un chiffre qu'on ne défend pas.
    en_attente = ref.get("en_attente", {}).get(nom)

    def verifier(cle: str, valeur: float, attendu: float, libelle: str,
                 cle_ecart: str | None = None) -> None:
        """Compare une ligne, en retirant d'abord l'écart documenté s'il y en a un."""
        nonlocal rc
        ecart = valeur - attendu
        documente = (ref.get("ecarts_documentes", {}).get(nom, {})
                     .get(cle_ecart or cle))
        if documente is None:
            print(f"      {libelle} {valeur:.2f} (Quadra {attendu:.2f}, écart {ecart:+.2f})")
            reste = ecart
        else:
            reste = ecart - documente
            print(f"      {libelle} {valeur:.2f} (Quadra {attendu:.2f}, écart {ecart:+.2f} "
                  f"dont {documente:+.2f} documenté, reste {reste:+.2f})")
        if abs(reste) > _tolerance(mois, cle) and not en_attente:
            print(f"::error::{nom} {mois:02d}/{YEAR} : {libelle} hors tolérance ({reste:+.2f})")
            rc = 1

    brut = float(data.get("salaire_brut") or 0)
    en_tete = data.get("en_tete") or {}
    ecart = brut - ref["brut"][nom]
    etat = "OK" if abs(ecart) <= _tolerance(mois, "brut") else ("ATTENTE" if en_attente else "ECART")
    print(f"\n{etat:5s} {nom:10s} brut {brut:.2f} — Quadra {ref['brut'][nom]:.2f} — écart {ecart:+.2f} ; "
          f"fenêtre {en_tete.get('date_debut_variables')} → {en_tete.get('date_fin_variables')} ; {res.status}")
    if etat == "ECART":
        rc = 1
    if en_attente:
        print(f"      EN ATTENTE — {en_attente}")
    fenetre_attendue = ref["fenetre"]
    if (en_tete.get("date_debut_variables"), en_tete.get("date_fin_variables")) != fenetre_attendue:
        print(f"::error::{nom} {mois:02d}/{YEAR} : fenêtre des variables inattendue "
              f"(attendu {fenetre_attendue[0]} → {fenetre_attendue[1]})")
        rc = 1

    for ligne in data.get("calcul_du_brut") or []:
        lib = str(ligne.get("libelle", ""))
        if "suppl" in lib.lower() and "structur" not in lib.lower():
            print(f"      HS      {lib[:50]:50s} q={ligne.get('quantite')} +{ligne.get('gain')}")
    for cle in ("details_absences", "details_conges"):
        for ligne in data.get(cle) or []:
            print(f"      {cle[8:15]:7s} {str(ligne.get('libelle'))[:50]:50s} "
                  f"q={ligne.get('quantite')} -{ligne.get('perte')} +{ligne.get('gain')}")

    synthese = data.get("synthese_net") or {}
    net = float(synthese.get("net_social_avant_impot") or 0)
    pas = float((synthese.get("impot_prelevement_a_la_source") or {}).get("montant") or 0)
    q_net, q_pas = ref["net"][nom]
    verifier("net", net, q_net, "net à payer avant impôt")
    verifier("pas", pas, q_pas, "impôt à la source")
    print(f"      net après impôt {net - pas:.2f} (Quadra {q_net - q_pas:.2f})")
    verifier("net_social", float(synthese.get("montant_net_social") or 0),
             ref["net_social"][nom], "montant net social")
    verifier("net_hs_exo", float(synthese.get("montant_net_hs_exonerees") or 0),
             ref["net_hs_exo"][nom], "net des heures sup exonérées")

    parametres = data.get("parametres") or {}
    verifier("smic", float(parametres.get("smic_horaire") or 0), SMIC_HORAIRE[mois],
             "SMIC horaire")
    verifier("pss", float(parametres.get("pss_mensuel") or 0), ref["pss"][nom], "plafond Sécu")

    cumuls = (data.get("cumuls") or {}).get("cumuls") or {}
    q_h, q_hs = ref["heures"][nom]
    verifier("heures", float(cumuls.get("heures_remunerees") or 0), q_h,
             "cumul heures", cle_ecart="cumul_heures")
    verifier("heures", float(cumuls.get("heures_supplementaires_remunerees") or 0), q_hs,
             "cumul h. sup", cle_ecart="cumul_hs")

    structure = data.get("structure_cotisations") or {}
    verifier("autres", float((structure.get("bloc_autres_contributions") or {}).get("total") or 0),
             ref["autres"][nom], "autres contributions employeur")
    for c in (structure.get("bloc_autres_contributions") or {}).get("lignes") or []:
        print(f"        {str(c.get('libelle'))[:46]:46s} {c.get('montant_patronal')}")

    allegements = structure.get("bloc_allegements") or []

    def montant(coti_id: str) -> float:
        return next((float(c.get("montant_patronal") or 0.0)
                     for c in allegements if c.get("coti_id") == coti_id), 0.0)

    verifier("deduction", montant("deduction_hs_patronale"), ref["deduction"][nom],
             "déduction forfaitaire HS")
    verifier("reduction", montant("reduction_generale"), ref["reduction"][nom],
             "réduction générale")

    for w in res.warnings or []:
        print(f"      avertissement : {w}")
    return rc


def _jouer_le_mois(emps: dict, mois: int) -> int:
    print(f"\n{'=' * 62}\n=== {mois:02d}/{YEAR} : état posé puis bulletins générés\n{'=' * 62}")
    apply_month("Colorplast", YEAR, mois)
    _remettre_a_zero_le_cumul_d_entree(emps, mois)
    if mois == 1:
        poser_les_feuilles(emps)
    rc = 0
    for nom in _salaries_du_mois(mois):
        try:
            res = _generer(emps[nom]["id"], mois)
        except PayslipBadRequestError as exc:
            print(f"::error::{nom} {mois:02d}/{YEAR} : {exc}")
            rc = 1
            continue
        rc |= _controler(nom, mois, _bulletin(emps[nom]["id"], mois), res)
    if mois == 1:
        # La fenêtre de février démarre le 26 janvier : elle relit la dernière
        # semaine de janvier, où les feuilles viennent d'être posées. Ce
        # pointage n'est pas celui que le cabinet a retenu pour février (Bugny
        # y fait 45,5 h, Gautheron n'a pas de feuille du tout). Une fois le
        # bulletin de janvier écrit, on l'efface : la fenêtre de février repart
        # du planning contractuel, c'est-à-dire de la saisie du cabinet.
        admin = get_supabase_admin_client()
        for nom in _salaries_du_mois(1):
            _clear_actual(admin, emps[nom]["id"], YEAR, 1)
        print("\n  pointages de janvier effacés : la fenêtre de février repart du planning")
    return rc


def main() -> int:
    apply = "--apply" in sys.argv
    dernier_mois = max(REFERENCES)
    if "--jusqu-a" in sys.argv:
        dernier_mois = int(sys.argv[sys.argv.index("--jusqu-a") + 1])
    mois_joues = [m for m in sorted(REFERENCES) if m <= dernier_mois]
    if not mois_joues:
        print(f"::error::Aucun mois de référence jusqu'à {dernier_mois}.")
        return 1

    emps = {
        e["last_name"]: e
        for e in (supabase.table("employees").select("id, last_name")
                  .eq("company_id", COMPANY_ID).in_("last_name", list(SALARIES)).execute()).data or []
    }
    if not apply:
        print(f"SIMULATION : rien n'est écrit. Mois à rejouer : {mois_joues}")
        for mois in mois_joues:
            ref = REFERENCES[mois]
            print(f"  {mois:02d}/{YEAR} — fenêtre {ref['fenetre'][0]} → {ref['fenetre'][1]}")
            for nom in _salaries_du_mois(mois):
                net, pas = ref["net"][nom]
                print(f"    {nom:10s} brut {ref['brut'][nom]:8.2f} ; "
                      f"net avant impôt {net:8.2f} ; impôt {pas:6.2f}")
        return 0

    manquants = sorted({nom for mois in mois_joues for nom in _salaries_du_mois(mois)} - set(emps))
    if manquants:
        print(f"::error::Salariés introuvables : {manquants}")
        return 1

    emp_avant, hist_avant = _snapshot([e["id"] for e in emps.values()])
    print("=== Fiches relevées avant ===")
    for e in emp_avant.values():
        print(f"  {e['last_name']:10s} salaire_de_base={e.get('salaire_de_base')}")
    rc = 0
    try:
        print("\n=== Doublons de la base de test retirés ===")
        _nettoyer_les_doublons_du_cabinet(emps, mois_joues)
        for mois in mois_joues:
            rc |= _jouer_le_mois(emps, mois)
    finally:
        print("\n=== Fiches remises comme avant ===")
        _restaurer(emp_avant, hist_avant)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
