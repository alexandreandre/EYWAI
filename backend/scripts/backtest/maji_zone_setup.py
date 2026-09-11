#!/usr/bin/env python3
"""Setup data-driven du backtest MAJI / ZONE 404, janvier-juin 2026.

Deux volets, tous deux idempotents :

* ``--config`` : la configuration PERMANENTE des fiches (statut, forfait,
  mutuelle, prévoyance, historique de salaire daté, ancienneté), lue sur les
  bulletins réels du cabinet (``data/<societe>/bulletins/<AAAA-MM>/md``) et les
  DSN. Elle vaut pour tous les mois, passés et futurs.
* ``--month M`` : les données du MOIS (jours de CP / absences au calendrier,
  saisies mensuelles : primes, notes de frais, acomptes ; réglages « flippés »
  par mois : taux PAS, titres-restaurant, transport, rémunération de mois
  partiel). Les saisies portent le marqueur ``BACKTEST_AUTO_MAJI_ZONE`` et sont
  purgées avant réinsertion.

Usage :
    .venv/bin/python -m scripts.backtest.maji_zone_setup --company Maji --config
    .venv/bin/python -m scripts.backtest.maji_zone_setup --company Maji --month 2 [--emp BOUALI]
    .venv/bin/python -m scripts.backtest.maji_zone_setup --company Zone --month 1
"""
from __future__ import annotations

import argparse
import copy
from typing import Any, Dict, List

from app.core.database import get_supabase_admin_client, supabase
from scripts.backtest.employee_matching import resolve_company_id

MARKER = "BACKTEST_AUTO_MAJI_ZONE"

NDF = "Rbst note de frais"  # net-only, hors MNS (SNDF Cegid, cf. classifieur frais pro)

# ---------------------------------------------------------------------------
# Prévoyance (taux lus sur les bulletins : EPRD/EPRE non-cadre APICIL, EPRA/EPRB
# cadre APICIL chez MAJI ; EPR1/EPR2 GAN chez ZONE 404).
# ---------------------------------------------------------------------------
PREV_MAJI_NC = [
    {"id": "prev_nc_ta", "base": "brut_plafonne", "libelle": "Prévoyance NC APICIL TA",
     "salarial": 0.00375, "patronal": 0.00375},
]
PREV_MAJI_NC_TB = PREV_MAJI_NC + [
    {"id": "prev_nc_tb", "base": "tranche_2", "libelle": "Prévoyance NC APICIL TB",
     "salarial": 0.00675, "patronal": 0.00675},
]
PREV_MAJI_CADRE = [
    {"id": "prev_cadre_ta", "base": "brut_plafonne", "libelle": "Prévoyance cadre APICIL TA",
     "salarial": 0.0, "patronal": 0.0169},
    {"id": "prev_cadre_tb", "base": "tranche_2", "libelle": "Prévoyance cadre APICIL TB",
     "salarial": 0.01206, "patronal": 0.00804},
]
PREV_ZONE = [
    {"id": "prev_nc_ta", "base": "brut_plafonne", "libelle": "Prévoyance non cadre GAN TA",
     "salarial": 0.0037, "patronal": 0.0037},
]
PREV_ZONE_TB = PREV_ZONE + [
    {"id": "prev_nc_tb", "base": "tranche_2", "libelle": "Prévoyance GAN TB",
     "salarial": 0.00775, "patronal": 0.00775},
]

MUTUELLE_LIBELLE = {
    "Maji": "Mutuelle Apicil 17.62€ / 17.62€",
    "Zone": "Mutuelle 13.42€ / 13.42€",
}

# Théo BARBERET chez MAJI : CDI 23/01→28/02/2026, puis CDD 29→30/06/2026, UNE
# fiche (NIR unique par société). Dates basculées par mois avant génération.
BARBERET_CDI = {"hire": "2026-01-23", "end": "2026-02-28", "type": "CDI"}
BARBERET_CDD = {"hire": "2026-06-29", "end": "2026-06-30", "type": "CDD"}

# Diviseur de valorisation d'une journée d'absence en forfait jour chez ces
# cabinets : base / 22 (Cegid), au lieu de la moyenne légale 21,67.
COMPANY_SETTINGS = {"forfait_jours_ouvres_mois": 22}

from datetime import date as _d  # noqa: E402

FERIES_2026 = {
    _d(2026, 1, 1), _d(2026, 4, 6), _d(2026, 5, 1), _d(2026, 5, 8), _d(2026, 5, 14),
    _d(2026, 5, 25), _d(2026, 7, 14), _d(2026, 8, 15), _d(2026, 11, 1), _d(2026, 11, 11),
    _d(2026, 12, 25),
}

# Part patronale de mutuelle réintégrée au net imposable ? Lu sur les bulletins :
# ZONE 404 : net imposable = brut − retenues (jamais réintégrée, janv.→mai).
MUT_REINT_IMPOT = {"Maji": True, "Zone": False}

# ---------------------------------------------------------------------------
# Configuration permanente par salarié.
#   statut, forfait, duree (h/semaine), temps_partiel, mutuelle (bool),
#   prev (liste ou None), base (salaire courant), salary_history
#   [(ancien, nouveau, effective_date)], contract_end, seniority_ref,
#   drop_dsn_anciennete.
# ---------------------------------------------------------------------------
PERMANENT: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Maji": {
        "AMATE": {"statut": "Cadre", "forfait": True, "mutuelle": False, "prev": PREV_MAJI_CADRE,
                  "base": 3551.41},
        "ANDRE": {"statut": "Cadre", "forfait": True, "mutuelle": True, "prev": PREV_MAJI_CADRE,
                  "base": 6666.66},
        # CDD du 29-30/06 (fiche existante) : non-cadre sur les bulletins (EPRD NC).
        "BARBERET": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_MAJI_NC,
                     "base": 3000.0},
        # 8,08 h/semaine sur le contrat ; le cabinet mensualise 35,00 h à 15,00 €
        # (525 €) : 8,0769 h/semaine donne exactement 35,00 h et 15,00 €/h.
        "BLA": {"statut": "Non-Cadre", "forfait": False, "duree": 8.0769, "temps_partiel": True,
                "mutuelle": True, "prev": PREV_MAJI_NC, "base": 525.0},
        "BOUALI": {"statut": "Non-Cadre", "forfait": True, "mutuelle": False, "prev": PREV_MAJI_NC,
                   "base": 3045.0, "salary_history": [(2900.0, 3045.0, "2026-02-01")]},
        "BOULAY": {"statut": "Non-Cadre", "forfait": False, "duree": 31.0, "temps_partiel": True,
                   "mutuelle": False, "prev": PREV_MAJI_NC, "base": 2500.0},
        # Sortie le 21/06/2026 (DSN bloc 62, motif 059) ; absente de la liste du
        # personnel de juillet transmise par Vanessa.
        "FERCHAUT": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_MAJI_NC,
                     "base": 2875.0, "salary_history": [(2526.55, 2875.0, "2026-02-01")],
                     "contract_end": "2026-06-21"},
        "HART": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_MAJI_NC_TB,
                 "base": 4166.66},
        # 39 h : le salaire mensuel INCLUT les 17,33 h structurelles à 25 %
        # (2 552,16 + 364,52 = 2 916,68) ; le moteur en déduit le taux horaire
        # 16,8271 = 2 916,68 / 173,33 h équivalentes, comme le cabinet.
        "JOLLY": {"statut": "Cadre", "forfait": False, "duree": 39.0, "mutuelle": True,
                  "prev": PREV_MAJI_CADRE, "base": 2916.68, "contract_end": "2026-02-20"},
        "PELLET": {"statut": "Non-Cadre", "forfait": False, "duree": 35.0, "mutuelle": False,
                   "prev": PREV_MAJI_NC, "base": 2300.0, "contract_end": "2026-03-12"},
        "SMITH": {"statut": "Non-Cadre", "forfait": True, "temps_partiel": True, "duree": 7.0,
                  "mutuelle": False, "prev": None, "base": 1396.18},
        "VERNYC": {"statut": "Non-Cadre", "forfait": False, "duree": 35.0, "mutuelle": True,
                   "prev": PREV_MAJI_NC, "base": 2300.0},
        # Mutuelle jusqu'en avril : plus de part patronale déclarée (DSN code 92) en mai-juin.
        "VIRTH": {"statut": "Non-Cadre", "forfait": True, "mutuelle": False, "mutuelle_jusqua": 4,
                  "prev": PREV_MAJI_NC,
                  "base": 3045.0, "salary_history": [(2856.61, 3045.0, "2026-02-01")],
                  "drop_dsn_anciennete": True},
    },
    "Zone": {
        "AGOUMBI": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_ZONE,
                    "base": 3608.0, "salary_history": [(3500.0, 3608.0, "2026-03-01")]},
        "ASSANHAJI": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_ZONE,
                      "base": 3608.0, "salary_history": [(3500.0, 3608.0, "2026-03-01")]},
        "BARAN": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_ZONE_TB,
                  "base": 5000.0},
        # Transfert MAJI -> ZONE 404 sans solde de tout compte : ancienneté du 23/01/2026.
        "BARBERET": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_ZONE,
                     "base": 3000.0, "seniority_ref": "2026-01-23"},
        "FILLINGER": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_ZONE_TB,
                      "base": 3166.66},
        "PERRIER": {"statut": "Non-Cadre", "forfait": True, "mutuelle": True, "prev": PREV_ZONE,
                    "base": 3750.0},
    },
}

# Taux PAS par mois (DSN S21.G00.50.006 / .007) : (taux %, type). Flippé avant
# chaque génération : le champ est partagé entre les mois.
PAS: Dict[str, Dict[str, Dict[int, tuple]]] = {
    "Maji": {
        "AMATE": {m: (3.8, "01") for m in range(1, 7)},
        "ANDRE": {1: (10.5, "01"), **{m: (13.3, "01") for m in range(2, 7)}},
        "BARBERET": {1: (0.0, "01"), 2: (0.0, "01"), 6: (0.0, "13")},
        "BLA": {5: (0.0, "13"), 6: (0.0, "01")},
        "BOULAY": {4: (0.0, "13"), 5: (0.0, "01"), 6: (0.0, "01")},
        "FERCHAUT": {1: (3.5, "13"), 2: (13.8, "13"), 3: (4.3, "01"), 4: (4.3, "01"),
                     5: (1.5, "01"), 6: (1.5, "01")},
        "HART": {m: (0.0, "01") for m in range(4, 7)},
        "JOLLY": {1: (2.7, "01"), 2: (2.7, "01")},
        "BOUALI": {m: (4.0, "01") for m in range(1, 7)},
        "PELLET": {m: (0.0, "01") for m in range(1, 4)},
        "SMITH": {5: (5.4, "01"), 6: (5.4, "01")},
        "VERNYC": {m: (1.1, "01") for m in range(1, 7)},
        "VIRTH": {m: (0.0, "01") for m in range(1, 7)},
    },
    "Zone": {
        "AGOUMBI": {**{m: (0.0, "01") for m in range(1, 6)}, 6: (6.1, "01")},
        "ASSANHAJI": {m: (3.1, "01") for m in range(1, 7)},
        "BARAN": {3: (9.9, "13"), 4: (11.9, "13"), 5: (13.8, "13"), 6: (13.8, "13")},
        "BARBERET": {m: (0.0, "01") for m in range(3, 7)},
        "FILLINGER": {4: (0.0, "13"), 5: (5.3, "13"), 6: (5.3, "13")},
        "PERRIER": {3: (1.0, "01"), **{m: (8.1, "01") for m in range(4, 7)}},
    },
}

# ---------------------------------------------------------------------------
# Données mensuelles. Clés :
#   cp        : jours de congés payés (int, ou (jour, 0.5) pour une demi-journée)
#   maladie   : jours d'arrêt maladie (forfait : 1 jour chacun)
#   abs_days  : jours d'absence non rémunérée (forfait : 1 jour chacun)
#   abs_h     : {jour: heures} absence non rémunérée (salariés à l'heure)
#   partiel   : remuneration_mois_partiel (surcharge du mois, salariés à l'heure)
#   inputs    : [(libellé, montant, soumis_cotis, imposable)]
#   tr        : nombre de titres-restaurant du mois (9,00 € : 5,40 pat. / 3,60 sal.)
#   transport : abonnement mensuel total (remboursé à 50 %)
# ---------------------------------------------------------------------------
MONTH_DATA: Dict[str, Dict[int, Dict[str, Dict[str, Any]]]] = {
    "Maji": {
        1: {
            "AMATE": {"cp": [2], "inputs": [(NDF, 566.58, False, False)]},
            "ANDRE": {"cp": [2, 26, 27, 28], "maladie": [29, 30]},
            "BARBERET": {"contrat": BARBERET_CDI},
            "BOUALI": {"inputs": [(NDF, 99.79, False, False)]},
            "FERCHAUT": {"inputs": [(NDF, 189.60, False, False)]},
            "JOLLY": {"heures_jour": 7.8},
            "PELLET": {"abs_h": {2: 7.0, 28: 7.0, 29: 7.0, 30: 7.0}},
            "VERNYC": {"partiel": {"heures_base": 140.0}},
            "VIRTH": {"inputs": [(NDF, 86.19, False, False)]},
        },
        2: {
            "AMATE": {"inputs": [(NDF, 566.58, False, False)]},
            "ANDRE": {"maladie": [2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 23, 24, 25, 26, 27],
                      "inputs": [("Avance sur salaire", 3819.33, False, False)]},
            "BARBERET": {"contrat": BARBERET_CDI,
                         "inputs": [(NDF, 1487.01, False, False),
                                    ("Acompte avance frais 02/2026", -1000.0, False, False)]},
            "BOUALI": {"cp": [5, 6, 9, 10, 11, 12, 13, 16],
                       "inputs": [("Régul augmentation 01/2026", 145.0, True, True),
                                  ("Paiement solde heures récup 25%", 1475.86, True, True),
                                  (NDF, 37.99, False, False)]},
            "FERCHAUT": {"inputs": [("Régul augmentation 01/2026", 348.45, True, True),
                                    ("Paiement heures récup 25%", 2160.36, True, True),
                                    (NDF, 641.16, False, False)]},
            # Sortie le 20/02 : le cabinet paie 105 h de base + 12 h structurelles
            # (quantités réelles du bulletin), pas un prorata calendaire.
            "JOLLY": {"heures_jour": 7.8,
                      "partiel": {"heures_base": 105.0, "heures_hs_structurelles": 12.0},
                      "inputs": [("Indemnité compensatrice de congés payés", 1343.36, True, True),
                                 (NDF, 198.48, False, False)]},
            "PELLET": {"inputs": [("Régul 01/2026", 45.49, True, True),
                                  (NDF, 29.42, False, False)]},
            "VERNYC": {"inputs": [(NDF, 240.55, False, False)]},
            "VIRTH": {"inputs": [("Régul augmentation 01/2026", 188.39, True, True),
                                 ("Paiement heures récup 25%", 829.89, True, True),
                                 (NDF, 44.99, False, False)]},
        },
        3: {
            "AMATE": {"inputs": [(NDF, 566.58, False, False)]},
            "ANDRE": {"maladie": [2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 16, 17, 18, 19, 20, 23, 24, 25, 26, 27, 30, 31],
                      "inputs": [("Avance sur salaire", 3232.18, False, False)]},
            "BOUALI": {"inputs": [(NDF, 163.45, False, False)]},
            "FERCHAUT": {"inputs": [(NDF, 953.19, False, False)]},
            "PELLET": {"partiel": {"heures_base": 60.67},
                       "inputs": [("Indemnité compensatrice de congés payés", 636.83, True, True)]},
            "VERNYC": {"inputs": [(NDF, 131.18, False, False)]},
            "VIRTH": {"cp": [20], "inputs": [(NDF, 44.99, False, False)]},
        },
        4: {
            "AMATE": {"cp": [13, 14, 15], "inputs": [(NDF, 583.46, False, False)]},
            # Arrêt 01-10/04 intégralement maintenu par le cabinet (retenue de 8 j
            # dont le lundi de Pâques, remise par une ligne « Maintien de salaire »).
            # Posé pour que le plafond soit réduit des 10 jours calendaires ; le
            # férié étant payé (ancienneté > 3 mois), 7 jours sont retenus ici et
            # le maintien vaut 7 × 303,03 : le brut est le même (base pleine).
            "ANDRE": {"maladie": [1, 2, 3, 7, 8, 9, 10],
                      "inputs": [("Maintien de salaire", 2121.21, True, True),
                                 ("Régul salaire 02+03/2026", 8937.07, True, True),
                                 ("Acomptes", -7051.51, False, False)]},
            "BOUALI": {"cp": [2, 3], "inputs": [(NDF, 58.79, False, False)]},
            "BOULAY": {"partiel": {"heures_base": 24.33}, "inputs": [(NDF, 487.01, False, False)]},
            "FERCHAUT": {"inputs": [(NDF, 398.00, False, False)]},
            "HART": {},
            "VERNYC": {"inputs": [(NDF, 208.56, False, False)]},
            "VIRTH": {"inputs": [(NDF, 582.46, False, False)]},
        },
        5: {
            "AMATE": {"cp": [15], "inputs": [("Prime bilan", 1600.0, True, True),
                                             (NDF, 566.58, False, False)]},
            "ANDRE": {"inputs": [(NDF, 467.12, False, False)]},
            "BLA": {"partiel": {"heures_base": 16.0}},
            "BOUALI": {"cp": [15], "inputs": [(NDF, 164.84, False, False)]},
            # BOULAY 7/7/3/7/7 : les fériés du vendredi 08 et du jeudi 14 valent 7 h.
            # « Remboursement transport » 11,25 : compté dans le MNS par le cabinet
            # (contrairement au « RBST TRANSPORT 50 % » de ZONE 404) → prime non soumise.
            "BOULAY": {"abs_h": {25: 7.0}, "ferie_h": {8: 7.0, 14: 7.0},
                       "inputs": [("Remboursement transport", 11.25, False, False)]},
            "FERCHAUT": {"cp": [7, 11, 12, 13, 15], "inputs": [(NDF, 241.40, False, False)]},
            "HART": {},
            # SMITH 7 h/semaine, le lundi : les fériés du 08 et du 14 tombent sur
            # des jours non travaillés (le cabinet ne les retient pas).
            "SMITH": {"pattern": {"jours": [0], "heures": 7.0}},
            "VERNYC": {"cp": [4, 25], "inputs": [(NDF, 275.53, False, False)]},
            "VIRTH": {"cp": [15, 18, (19, 0.5)],
                      "inputs": [("Prime de bilan", 1400.0, True, True),
                                 (NDF, 122.89, False, False)]},
        },
        # Juin : pas de bulletins du cabinet (DSN seule) ; BARBERET repasse en CDD.
        6: {
            "AMATE": {"inputs": [(NDF, 566.58, False, False)]},
            "ANDRE": {}, "HART": {}, "VIRTH": {},
            # DSN : 36 h déclarées pour 35 mensualisées → 1 h complémentaire à 10 % (16,50).
            "BLA": {"inputs": [("Heure complémentaire majorée 10%", 16.50, True, True)]},
            "BOULAY": {"inputs": [("Remboursement transport", 11.25, False, False)]},
            "BARBERET": {"contrat": BARBERET_CDD},
            "BOUALI": {"inputs": [(NDF, 58.79, False, False)]},
            # Sortie le 21/06 : brut DSN 6 241,73 = 15/22 × 2 875 + 4 281,50 d'indemnités
            # de fin de contrat (CP + rupture), posées en une prime soumise.
            "FERCHAUT": {"inputs": [("Indemnités de fin de contrat (CP, rupture)", 4281.50, True, True),
                                    (NDF, 513.73, False, False)]},
            "SMITH": {"pattern": {"jours": [0], "heures": 7.0}},
            "VERNYC": {"inputs": [(NDF, 74.74, False, False)]},
        },
    },
    "Zone": {
        1: {
            "AGOUMBI": {"tr": 17, "transport": 73.0,
                        "inputs": [(NDF, 1487.48, False, False), ("Acompte 01/2026", -2000.0, False, False)]},
            "ASSANHAJI": {"tr": 17,
                          "inputs": [(NDF, 811.64, False, False), ("Acompte 01/2026", -2000.0, False, False)]},
        },
        2: {
            "AGOUMBI": {"tr": 20, "transport": 73.0,
                        "inputs": [(NDF, 1912.14, False, False),
                                   ("Acompte avance frais 02/2026", -1148.0, False, False)]},
            "ASSANHAJI": {"tr": 19, "inputs": [(NDF, 486.13, False, False)]},
        },
        3: {
            "AGOUMBI": {"inputs": [(NDF, 824.11, False, False)]},
            "ASSANHAJI": {"abs_days": [16, 17, 18, 19, 20], "inputs": [(NDF, 484.14, False, False)]},
            "BARAN": {"inputs": [(NDF, 539.98, False, False)]},
            "BARBERET": {},
            "PERRIER": {},
        },
        4: {
            "AGOUMBI": {"transport": 73.0, "inputs": [(NDF, 296.54, False, False)]},
            "ASSANHAJI": {},
            "BARAN": {"cp": [21], "inputs": [(NDF, 433.20, False, False)]},
            "BARBERET": {},
            "FILLINGER": {},
            "PERRIER": {"inputs": [(NDF, 1034.08, False, False)]},
        },
        5: {
            "AGOUMBI": {"cp": [(13, 0.5)],
                        "inputs": [("Prime de déménagement", 1000.0, True, True), (NDF, 141.05, False, False)]},
            "ASSANHAJI": {"inputs": [("Prime de déménagement", 1000.0, True, True)]},
            "BARAN": {"cp": [12],
                      "inputs": [("Prime de déménagement", 1000.0, True, True), (NDF, 946.21, False, False)]},
            "BARBERET": {},
            "FILLINGER": {},
            "PERRIER": {},
        },
        # Juin : DSN seule (taux PAS du mois pour tous ; AGOUMBI passe à 6,1 %).
        6: {
            "AGOUMBI": {}, "ASSANHAJI": {}, "BARAN": {}, "FILLINGER": {}, "PERRIER": {},
            # Sortie le 21/06 (DSN bloc 62) : brut 4 122,05 = 15/22 × 3 000 + 2 076,60
            # d'indemnités de fin de contrat (solde de tout compte, CP).
            "BARBERET": {"inputs": [("Indemnités de fin de contrat (CP)", 2076.60, True, True)]},
        },
    },
}


# ---------------------------------------------------------------------------
# Accès base
# ---------------------------------------------------------------------------
def _emp_map(company_id: str) -> Dict[str, dict]:
    rows = (supabase.table("employees").select("*").eq("company_id", company_id).execute().data)
    out: Dict[str, dict] = {}
    by_mat: Dict[str, List[dict]] = {}
    for r in rows:
        if not r.get("matricule"):
            continue  # fiche technique sans matricule (ex. « Test ACTIVATION » sur le test)
        by_mat.setdefault(r["matricule"], []).append(r)
    for mat, lst in by_mat.items():
        if len(lst) == 1:
            out[mat] = lst[0]
            continue
        # Deux fiches pour un même matricule (BARBERET chez MAJI : CDI 01-02/2026
        # puis CDD 06/2026) : la plus récente garde le matricule nu, chacune est
        # aussi accessible par <MATRICULE>_<TYPE>.
        lst.sort(key=lambda r: str(r.get("hire_date") or ""))
        out[mat] = lst[-1]
        for r in lst:
            out[f"{mat}_{(r.get('contract_type') or '').upper()}"] = r
    return out


MUTUELLE_BAREMES = {
    # libellé -> (part salariale, part patronale) lus sur les bulletins (EMUT)
    "Mutuelle Apicil 17.62€ / 17.62€": (17.62, 17.62),
    "Mutuelle 13.42€ / 13.42€": (13.42, 13.42),
}


def _mutuelle_type_id(admin, company_id: str, libelle: str) -> str:
    """Le barème réel de la société, créé s'il manque (la base de test a été
    copiée de la prod avant sa création)."""
    rows = (admin.table("company_mutuelle_types").select("id, libelle")
            .eq("company_id", company_id).eq("libelle", libelle).execute().data)
    if rows:
        return rows[0]["id"]
    if libelle not in MUTUELLE_BAREMES:
        raise SystemExit(f"Barème mutuelle '{libelle}' introuvable pour {company_id}")
    sal, pat = MUTUELLE_BAREMES[libelle]
    created = admin.table("company_mutuelle_types").insert({
        "company_id": company_id, "libelle": libelle,
        "montant_salarial": sal, "montant_patronal": pat,
        "part_patronale_soumise_a_csg": True, "part_salariale_deductible_impot": True,
        "is_active": True, "pack_couverture": "autre", "statut_categoriel": "tous",
        "source": "dsn_import", "note": "Grille cabinet EMUT — bulletins 2026",
    }).execute().data
    print(f"[{libelle}] barème créé")
    return created[0]["id"]


def _salaire_payload(emp: dict, valeur: float) -> dict:
    sdb = copy.deepcopy(emp.get("salaire_de_base") or {"type": "mensuel"})
    sdb["type"] = sdb.get("type", "mensuel")
    sdb["valeur"] = valeur
    return sdb


def _set_salary_history(admin, emp: dict, ancien: float, nouveau: float, effective_date: str) -> None:
    """Une ligne par augmentation ; le rappel a déjà été payé par le cabinet."""
    template = copy.deepcopy(emp.get("salaire_de_base") or {"type": "mensuel"})
    template["type"] = template.get("type", "mensuel")
    template.pop("a_verifier", None)
    ancien_p = {**template, "valeur": ancien}
    nouveau_p = {**template, "valeur": nouveau, "rappel_deja_verse": True}
    existing = (admin.table("salary_history").select("id")
                .match({"employee_id": emp["id"], "effective_date": effective_date})
                .execute().data)
    payload = {"company_id": emp["company_id"], "ancien_salaire": ancien_p,
               "nouveau_salaire": nouveau_p,
               "motif": "Historique contractuel (bulletins du cabinet) — backtest 2026"}
    if existing:
        admin.table("salary_history").update(payload).eq("id", existing[0]["id"]).execute()
    else:
        admin.table("salary_history").insert({**payload, "employee_id": emp["id"],
                                              "effective_date": effective_date,
                                              "created_by": None}).execute()


def apply_config(company: str, only: List[str] | None = None) -> None:
    admin = get_supabase_admin_client()
    company_id = resolve_company_id(company)
    emps = _emp_map(company_id)
    mut_id = _mutuelle_type_id(admin, company_id, MUTUELLE_LIBELLE[company])
    # Réglages société (diviseur forfait), fusionnés dans companies.settings.
    row = admin.table("companies").select("settings").eq("id", company_id).single().execute().data
    settings = copy.deepcopy(row.get("settings") or {})
    if any(settings.get(k) != v for k, v in COMPANY_SETTINGS.items()):
        settings.update(COMPANY_SETTINGS)
        admin.table("companies").update({"settings": settings}).eq("id", company_id).execute()
        print(f"[{company}] settings += {COMPANY_SETTINGS}")
    for mat, cfg in PERMANENT[company].items():
        if only and mat not in only:
            continue
        emp = emps.get(mat)
        if not emp:
            print(f"[{mat}] introuvable"); continue
        _apply_employee_config(admin, company, mat, emp, cfg, mut_id)


def _apply_employee_config(admin, company: str, mat: str, emp: dict, cfg: dict, mut_id: str) -> None:
    sp = copy.deepcopy(emp.get("specificites_paie") or {})
    # Mutuelle : un seul barème réel par société.
    mut = sp.get("mutuelle") or {}
    if cfg.get("mutuelle"):
        mut.update({"adhesion": True, "mutuelle_type_ids": [mut_id], "lignes_specifiques": []})
        # Réintégration de la part patronale au net imposable : le cabinet ne
        # la pratique pas chez ZONE 404 (net imposable = brut − retenues).
        mut["part_patronale_reintegree_impot"] = bool(MUT_REINT_IMPOT.get(company, True))
    else:
        mut = {"adhesion": False}
    sp["mutuelle"] = mut
    # Prévoyance : lignes spécifiques (taux des bulletins).
    if cfg.get("prev"):
        sp["prevoyance"] = {"adhesion": True, "lignes_specifiques": copy.deepcopy(cfg["prev"])}
    else:
        sp["prevoyance"] = {"adhesion": False}
    if cfg.get("drop_dsn_anciennete"):
        sp["dsn_anciennete"] = None
    update: Dict[str, Any] = {
        "specificites_paie": sp,
        "statut": cfg["statut"],
        "is_forfait_jour": bool(cfg["forfait"]),
        "prior_service_months": 0,
    }
    if "duree" in cfg:
        update["duree_hebdomadaire"] = cfg["duree"]
    if "temps_partiel" in cfg:
        update["is_temps_partiel"] = bool(cfg["temps_partiel"])
    if "contract_end" in cfg:
        update["contract_end_date"] = cfg["contract_end"]
    if "seniority_ref" in cfg:
        update["seniority_reference_date"] = cfg["seniority_ref"]
    if "base" in cfg:
        update["salaire_de_base"] = _salaire_payload(emp, cfg["base"])
    admin.table("employees").update(update).eq("id", emp["id"]).execute()
    for ancien, nouveau, eff in cfg.get("salary_history", []):
        _set_salary_history(admin, emp, ancien, nouveau, eff)
    print(f"[{mat}] statut={cfg['statut']} forfait={cfg['forfait']} mutuelle={bool(cfg.get('mutuelle'))} "
          f"prev={len(cfg.get('prev') or [])} base={cfg.get('base')} "
          f"hist={cfg.get('salary_history', [])}")


# ---------------------------------------------------------------------------
# Mois
# ---------------------------------------------------------------------------
def _set_calendar(admin, emp: dict, year: int, month: int, cfg: dict, forfait: bool) -> str:
    sch = (admin.table("employee_schedules").select("id,planned_calendar,actual_hours")
           .match({"employee_id": emp["id"], "year": year, "month": month})
           .maybe_single().execute())
    if not sch or not sch.data:
        return "NO_SCHEDULE"
    planned = copy.deepcopy(sch.data.get("planned_calendar") or {})
    cal = planned.get("calendrier_prevu", [])
    by_day = {j.get("jour"): j for j in cal}
    actions = []

    def _day(d: int) -> dict:
        j = by_day.get(d)
        if j is None:
            j = {"jour": d, "type": "travail", "heures_prevues": 7.0}
            cal.append(j); by_day[d] = j
        return j

    if cfg.get("pattern"):
        # Répartition hebdomadaire d'un temps partiel : jours travaillés (0 = lundi)
        # et heures par jour ; les autres jours de semaine deviennent des repos.
        # Un férié tombant sur un jour non travaillé n'a pas à être retenu.
        from datetime import date as _date
        pat = cfg["pattern"]
        hire = str(emp.get("hire_date") or "")[:10]
        for j in cal:
            try:
                jour = _date(year, month, int(j["jour"]))
            except (KeyError, TypeError, ValueError):
                continue
            wd = jour.weekday()
            if wd >= 5 or j.get("type") in ("conges_payes", "arret_maladie", "absence_non_remuneree"):
                continue
            if hire and jour.isoformat() < hire and (j.get("type") == "ferie" or jour in FERIES_2026):
                # Férié avant l'embauche : reste (ou redevient) un férié — le moteur
                # sait alors que l'entrée au premier jour ouvré vaut un mois complet.
                j["type"] = "ferie"; j["heures_prevues"] = 0.0
                continue
            if wd in pat["jours"]:
                if j.get("type") != "ferie":
                    j["type"] = "travail"
                j["heures_prevues"] = float(pat["heures"])
            else:
                j["type"] = "repos"; j["heures_prevues"] = 0.0
            j["manuel"] = True
        actions.append(f"pattern={pat['jours']}x{pat['heures']}h")
    for d, h in (cfg.get("ferie_h") or {}).items():
        # Heures que le salarié aurait faites ce jour férié (retenue d'un férié
        # non payé d'un temps partiel à répartition irrégulière : 7 h, pas 31/5).
        j = _day(d)
        j["type"] = "ferie"; j["heures_prevues"] = float(h); j["manuel"] = True
        actions.append(f"ferie:{d}={h}h")
    if cfg.get("heures_jour"):
        # Gabarit horaire du mois (ex. JOLLY 39 h : 7,8 h/jour, d'où les 17,33 h
        # structurelles mensualisées) — seuls les jours de travail sont réécrits.
        for j in cal:
            if j.get("type") == "travail":
                j["heures_prevues"] = float(cfg["heures_jour"])
        actions.append(f"heures_jour={cfg['heures_jour']}")
    for d in cfg.get("reset", []):
        # Jours retypés à tort par un import (ex. ANDRE avril : « sans solde »
        # importé depuis la DSN alors que le cabinet a maintenu le salaire).
        j = _day(d)
        if j.get("type") not in ("weekend", "ferie"):
            j["type"] = "travail"; j["manuel"] = True
            if not j.get("heures_prevues"):
                j["heures_prevues"] = 7.0
            actions.append(f"reset:{d}")
    for item in cfg.get("cp", []):
        d, quot = (item if isinstance(item, tuple) else (item, 1.0))
        j = _day(d)
        j["type"] = "conges_payes"; j["manuel"] = True
        if quot < 1:
            # Demi-journée : l'analyseur projette `quotite_absence` (0,5 jour de CP,
            # l'autre moitié travaillée), forfait comme horaire.
            j["quotite_absence"] = quot
        else:
            j.pop("quotite_absence", None)
        actions.append(f"cp:{d}{'/2' if quot < 1 else ''}")
    for d in cfg.get("maladie", []):
        j = _day(d)
        j["type"] = "arret_maladie"; j["manuel"] = True
        actions.append(f"mal:{d}")
    for d in cfg.get("abs_days", []):
        j = _day(d)
        j["type"] = "absence_non_remuneree"; j["manuel"] = True
        actions.append(f"abs:{d}")
    for d, h in (cfg.get("abs_h") or {}).items():
        j = _day(d)
        j["type"] = "absence_non_remuneree"; j["manuel"] = True; j["heures_prevues"] = round(h, 2)
        actions.append(f"abs:{d}={h}h")
    planned["calendrier_prevu"] = sorted(cal, key=lambda x: x["jour"])
    update = {"planned_calendar": planned}
    # Le pointage de repli (recopie du prévu) contredirait les jours posés : on le
    # vide pour le mois, le moteur retombe sur le calendrier prévu (régén-safe).
    ah = copy.deepcopy(sch.data.get("actual_hours") or {})
    if ah.get("calendrier_reel"):
        ah["calendrier_reel"] = []
        update["actual_hours"] = ah
        actions.append("actual-vidé")
    admin.table("employee_schedules").update(update).eq("id", sch.data["id"]).execute()
    return ",".join(actions) or "no-cal-change"


def _set_month_overrides(admin, emp: dict, year: int, month: int, cfg: dict, company: str, mat: str) -> List[str]:
    """Réglages partagés flippés au mois : PAS, titres-resto, transport, mois partiel."""
    current = admin.table("employees").select("specificites_paie").eq("id", emp["id"]).single().execute().data
    sp = copy.deepcopy(current.get("specificites_paie") or {})
    actions = []
    pas_cfg = PAS.get(company, {}).get(mat, {}).get(month)
    if pas_cfg:
        taux, typ = pas_cfg
        pas = sp.setdefault("prelevement_a_la_source", {})
        pas["taux"] = taux; pas["type_taux"] = typ; pas["source"] = "dsn"
        pas["periode"] = f"{year:04d}-{month:02d}"
        actions.append(f"pas={taux}/{typ}")
    tr = cfg.get("tr")
    sp["titres_restaurant"] = ({"beneficie": True, "valeur_faciale": 9.0, "part_patronale": 5.4,
                                "nombre_par_mois": int(tr)} if tr else {"beneficie": False, "nombre_par_mois": 0})
    if tr:
        actions.append(f"tr={tr}")
    transport = cfg.get("transport")
    sp["transport"] = {"abonnement_mensuel_total": float(transport or 0.0), "indemnite_mensuelle_nette": 0}
    if transport:
        actions.append(f"transport={transport}")
    # Fin d'adhésion mutuelle en cours d'année (VIRTH : plus de part patronale en
    # DSN à partir de mai) : adhésion posée selon le mois généré.
    jusqua = PERMANENT[company].get(mat, {}).get("mutuelle_jusqua")
    if jusqua is not None:
        mut = sp.get("mutuelle") or {}
        if month <= int(jusqua):
            mut_id = _mutuelle_type_id(admin, emp["company_id"], MUTUELLE_LIBELLE[company])
            mut.update({"adhesion": True, "mutuelle_type_ids": [mut_id], "lignes_specifiques": [],
                        "part_patronale_reintegree_impot": bool(MUT_REINT_IMPOT.get(company, True))})
        else:
            mut = {"adhesion": False}
        sp["mutuelle"] = mut
        actions.append(f"mutuelle={'oui' if month <= int(jusqua) else 'non'}")
    overrides = sp.setdefault("overrides_mensuels", {})
    key = f"{year:04d}-{month:02d}"
    if cfg.get("partiel"):
        overrides[key] = {"remuneration_mois_partiel": copy.deepcopy(cfg["partiel"])}
        actions.append(f"partiel={cfg['partiel']}")
    else:
        overrides.pop(key, None)
    admin.table("employees").update({"specificites_paie": sp}).eq("id", emp["id"]).execute()
    return actions


def _clear_inputs(admin, emp_id: str, year: int, month: int) -> None:
    admin.table("monthly_inputs").delete().match(
        {"employee_id": emp_id, "year": year, "month": month}
    ).like("description", f"%{MARKER}%").execute()


def _insert_input(admin, emp: dict, year: int, month: int, name: str, amount: float,
                  taxed: bool, taxable: bool) -> None:
    admin.table("monthly_inputs").insert({
        "employee_id": emp["id"], "company_id": emp["company_id"], "year": year, "month": month,
        "name": name, "description": f"Bulletin cabinet {month:02d}/{year} {MARKER}",
        "amount": amount, "is_socially_taxed": taxed, "is_taxable": taxable,
    }).execute()


def apply_month(company: str, year: int, month: int, only: List[str] | None = None) -> None:
    admin = get_supabase_admin_client()
    company_id = resolve_company_id(company)
    emps = _emp_map(company_id)
    data = MONTH_DATA.get(company, {}).get(month, {})
    for mat, cfg in data.items():
        if only and mat not in only:
            continue
        emp = emps.get(mat)
        if not emp:
            print(f"[{mat}] introuvable"); continue
        forfait = bool(PERMANENT[company].get(mat, {}).get("forfait", emp.get("is_forfait_jour")))
        if cfg.get("contrat"):
            # Même personne, plusieurs contrats dans la société (NIR unique par
            # société) : les dates du contrat en vigueur ce mois-là sont posées
            # avant la génération, le dernier contrat connu reste l'état final.
            c = cfg["contrat"]
            admin.table("employees").update({
                "hire_date": c["hire"], "contract_end_date": c["end"],
                "contract_type": c["type"],
            }).eq("id", emp["id"]).execute()
            emp = {**emp, "hire_date": c["hire"], "contract_end_date": c["end"]}
        cal = _set_calendar(admin, emp, year, month, cfg, forfait)
        ov = _set_month_overrides(admin, emp, year, month, cfg, company, mat)
        _clear_inputs(admin, emp["id"], year, month)
        for name, amount, taxed, taxable in cfg.get("inputs", []):
            _insert_input(admin, emp, year, month, name, amount, taxed, taxable)
        print(f"[{mat}] cal=[{cal}] {' '.join(ov)} inputs={len(cfg.get('inputs', []))}")


SCHEDULE_TEMPLATES = {
    # (société, forfait ?) -> matricule dont le calendrier prévu sert de gabarit
    ("Maji", True): "HART",
    ("Maji", False): "VERNYC",
    ("Zone", True): "AGOUMBI",
}


def ensure_schedules(company: str, year: int = 2026, months: range = range(1, 7)) -> None:
    """Crée les `employee_schedules` manquants (salariés partis ou jamais
    calendrisés : PELLET, BOUALI, JOLLY chez MAJI, BARAN chez ZONE 404) en
    copiant le calendrier prévu d'un gabarit du même régime. Sans calendrier,
    aucune absence ni CP ne peut être posé pour le mois."""
    from datetime import date

    admin = get_supabase_admin_client()
    company_id = resolve_company_id(company)
    emps = _emp_map(company_id)
    for mat, emp in emps.items():
        if "_" in mat:
            continue
        forfait = bool(PERMANENT[company].get(mat, {}).get("forfait", emp.get("is_forfait_jour")))
        tpl_mat = SCHEDULE_TEMPLATES.get((company, forfait)) or SCHEDULE_TEMPLATES[(company, True)]
        if tpl_mat == mat:
            continue
        # Tous les mois demandés, sans filtrer sur les dates de contrat : une
        # fiche peut porter plusieurs contrats dans l'année (BARBERET).
        for m in months:
            exist = (admin.table("employee_schedules").select("id")
                     .match({"employee_id": emp["id"], "year": year, "month": m}).execute().data)
            if exist:
                continue
            tpl = (admin.table("employee_schedules").select("planned_calendar")
                   .match({"employee_id": emps[tpl_mat]["id"], "year": year, "month": m})
                   .maybe_single().execute())
            if not tpl or not tpl.data:
                print(f"[{mat}] pas de gabarit {tpl_mat} pour {m:02d}/{year}"); continue
            admin.table("employee_schedules").insert({
                "employee_id": emp["id"], "company_id": company_id, "year": year, "month": m,
                "planned_calendar": tpl.data["planned_calendar"], "actual_hours": None,
                "payroll_events": {}, "cumuls": None,
            }).execute()
            print(f"[{mat}] calendrier {m:02d}/{year} créé (gabarit {tpl_mat})")


def prepare_maji(company: str = "Maji") -> None:
    """Préalables, idempotents :

    * calendriers manquants (cf. `ensure_schedules`) ;
    * MAJI : suppression des deux demandes « sans solde » d'ANDRE importées de
      la DSN — les bulletins portent un arrêt maladie (janv.-mars) et un
      maintien (avril).

    Théo BARBERET (CDI 23/01→28/02 puis CDD 29-30/06 chez MAJI) reste UNE fiche :
    le NIR est unique par société ; ses dates de contrat sont basculées par
    `apply_month` (clé `contrat`) avant la génération de chaque mois.
    """
    admin = get_supabase_admin_client()
    company_id = resolve_company_id(company)
    ensure_schedules(company)
    if company != "Maji":
        return
    andre = (admin.table("employees").select("id").eq("company_id", company_id)
             .eq("matricule", "ANDRE").single().execute().data)
    reqs = (admin.table("absence_requests").select("id,type,selected_days,comment")
            .eq("employee_id", andre["id"]).execute().data)
    for r in reqs:
        if r["type"] == "sans_solde" and (r.get("comment") or "").startswith("Import DSN"):
            admin.table("absence_requests").delete().eq("id", r["id"]).execute()
            print(f"[ANDRE] demande « sans solde » importée supprimée : {r['selected_days'][:2]}…")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True, choices=["Maji", "Zone"])
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int)
    ap.add_argument("--config", action="store_true")
    ap.add_argument("--prepare", action="store_true",
                    help="Préalables MAJI : fiche CDI BARBERET 01-02/2026, demandes ANDRE")
    ap.add_argument("--emp", nargs="*", default=None)
    args = ap.parse_args()
    if args.prepare:
        prepare_maji(args.company)
    if args.config:
        apply_config(args.company, only=args.emp)
    if args.month:
        apply_month(args.company, args.year, args.month, only=args.emp)
    if not args.config and not args.month and not args.prepare:
        ap.error("Préciser --prepare, --config et/ou --month M")


if __name__ == "__main__":
    main()
