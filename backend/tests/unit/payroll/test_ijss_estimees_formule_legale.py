"""IJSS estimées d'un arrêt maladie : formule et plafond légaux.

Règle (CSS R323-4 ; ameli, « Arrêt de travail pour maladie : les indemnités
journalières du salarié » ; référentiel du dépôt,
docs/audit-maji-2026/referentiel-legal-2026.md, R05) : l'IJ vaut 50 % du
salaire journalier de base, égal aux trois derniers salaires bruts ÷ 91,25,
chacun retenu dans la limite de 1,4 Smic mensuel pour les arrêts depuis le
01/04/2025 — le Smic en vigueur le dernier jour du mois civil qui précède
l'arrêt (12,02 € jusqu'au 31/05/2026, 12,31 € depuis le 01/06/2026).

Le moteur prenait le salaire de base contractuel ÷ 30,42, plafonné à
1,8 plafond de la Sécurité sociale journalier. Cas mesuré par l'enquête
(Colorplast, arrêt du 17/08) : 32,76 €/jour au lieu de 37,53 €/jour.
L'estimation garde son libellé « IJSS estimées » : le décompte de la caisse la
remplace dans le suivi IJSS.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

pytestmark = pytest.mark.unit

SMIC_2026 = {
    "cas_general": 12.31,
    "historique": [
        {"date_debut": "2026-01-01", "cas_general": 12.02},
        {"date_debut": "2026-06-01", "cas_general": 12.31},
    ],
}


def _ctx(salaire_base: float = 1993.40) -> SimpleNamespace:
    return SimpleNamespace(
        salaire_base_mensuel=salaire_base,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "smic": SMIC_2026,
            "ij_plafonds": {"maladie": 42.97, "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-09-13", "statut": "Non-Cadre"}},
    )


def _arret(debut: str, fin: str, salaires=None) -> dict:
    arret = {
        "arret_type": "maladie_simple",
        "date_debut": debut,
        "date_fin": fin,
        "subrogation_active": False,
        "nombre_enfants": 0,
        "salaire_periode_reelle": 0.0,
    }
    if salaires is not None:
        arret["salaires_bruts_reference"] = salaires
    return arret


REGLAGE = {"apply_legal_maintenance": False, "min_seniority_months": 12}


def _ijss(arret, periode, salaire_base: float = 1993.40):
    return calculer_maintien(arret, _ctx(salaire_base), REGLAGE, *periode)["ijss"]


def test_salaire_journalier_de_base_trois_derniers_bruts_sur_91_25():
    # Bruts de mai, juin et juillet ; arrêt débuté en août.
    ijss = _ijss(
        _arret("2026-08-17", "2026-08-31", [2432.78, 2327.64, 2089.06]),
        (date(2026, 8, 1), date(2026, 8, 31)),
    )
    sjb = (2432.78 + 2327.64 + 2089.06) / 91.25
    assert ijss["salaire_journalier_base"] == pytest.approx(sjb, abs=0.0001)
    assert ijss["ijss_journaliere"] == pytest.approx(37.53, abs=0.005)
    # 15 jours d'arrêt, 3 de carence : 12 jours indemnisés.
    assert ijss["nb_jours_indemnises"] == 12
    assert ijss["ijss_theorique"] == pytest.approx(round(sjb * 0.5 * 12, 2), abs=0.01)


def test_mois_sans_bulletin_compte_le_salaire_de_base():
    ijss = _ijss(
        _arret("2026-08-17", "2026-08-31", [None, 2327.64, 2089.06]),
        (date(2026, 8, 1), date(2026, 8, 31)),
    )
    sjb = (1993.40 + 2327.64 + 2089.06) / 91.25
    assert ijss["salaire_journalier_base"] == pytest.approx(sjb, abs=0.0001)


def test_sans_bruts_de_reference_trois_salaires_de_base():
    ijss = _ijss(_arret("2026-08-17", "2026-08-31"), (date(2026, 8, 1), date(2026, 8, 31)))
    assert ijss["salaire_journalier_base"] == pytest.approx(1993.40 * 3 / 91.25, abs=0.0001)


def test_plafond_de_1_4_smic_du_mois_qui_precede_l_arret():
    # Arrêt débuté en septembre 2026 : Smic du 31/08, 12,31 €.
    smic_mensuel = 12.31 * 35 * 52 / 12
    ijss = _ijss(
        _arret("2026-09-14", "2026-09-30", [5000.0, 5000.0, 5000.0]),
        (date(2026, 9, 1), date(2026, 9, 30)),
    )
    assert ijss["base_plafonnee"] == pytest.approx(1.4 * smic_mensuel * 3 / 91.25, abs=0.0001)
    assert ijss["ijss_journaliere"] == pytest.approx(42.97, abs=0.005)


def test_le_plafond_est_celui_du_debut_de_l_arret_pas_du_bulletin():
    # Arrêt débuté le 10/06/2026 : Smic du 31/05, 12,02 €, même si le
    # Smic a été revalorisé le 01/06.
    smic_mensuel = 12.02 * 35 * 52 / 12
    ijss = _ijss(
        _arret("2026-06-10", "2026-06-30", [5000.0, 5000.0, 5000.0]),
        (date(2026, 6, 1), date(2026, 6, 30)),
    )
    assert ijss["base_plafonnee"] == pytest.approx(1.4 * smic_mensuel * 3 / 91.25, abs=0.0001)
    assert ijss["ijss_journaliere"] == pytest.approx(41.95, abs=0.005)


def test_les_bruts_de_reference_sont_lus_sur_les_trois_bulletins_qui_precedent():
    from app.modules.payroll.infrastructure.salaires_de_reference import (
        salaires_bruts_de_reference,
    )

    lignes = [
        {"year": 2026, "month": 4, "salaire_brut": 9999.0},
        {"year": 2026, "month": 5, "salaire_brut": 2432.78},
        {"year": 2026, "month": 7, "salaire_brut": "2089.06"},
        {"year": 2026, "month": 8, "salaire_brut": 9999.0},
    ]

    class _Requete:
        def __init__(self):
            self.filtres = []

        def select(self, *a, **k):
            return self

        def eq(self, *a):
            self.filtres.append(("eq",) + a)
            return self

        def in_(self, *a):
            self.filtres.append(("in",) + a)
            return self

        def execute(self):
            return SimpleNamespace(data=lignes)

    requete = _Requete()
    client = SimpleNamespace(table=lambda nom: requete if nom == "payslips" else None)

    assert salaires_bruts_de_reference("emp-1", date(2026, 8, 17), client=client) == [
        2432.78,
        None,
        2089.06,
    ]
    assert ("eq", "employee_id", "emp-1") in requete.filtres


# --- Plafond appliqué à chaque paie (CSS R323-4, version du décret 2025-160) ---
#
# « il est tenu compte du revenu d'activité antérieur servant de base, lors de
# chaque paie, au calcul de la cotisation […] dans la limite d'un plafond égal
# à 1,4 fois le salaire minimum de croissance […] calculé pour un mois ».
# Chaque brut est retenu dans la limite de 1,4 Smic mensuel, puis la somme est
# divisée par 91,25 : plafonner le total laissait un mois au-dessus du
# plafond compenser un mois en dessous.

PLAFOND_MENSUEL_MAI_2026 = 1.4 * 12.02 * 35 * 52 / 12  # Smic du 30/04/2026


def _ancienne_base_plafonnee(bruts, plafond_mensuel):
    """Total des trois bruts plafonné à trois fois le plafond mensuel."""
    return min(sum(bruts), 3 * plafond_mensuel) / 91.25


def test_chaque_paie_est_plafonnee_cas_chiffre_de_comitech():
    # Février et mars sous le plafond, avril au-dessus ; arrêt débuté en mai.
    bruts = [2486.41, 2478.44, 2872.61]
    ijss = _ijss(
        _arret("2026-05-04", "2026-05-31", bruts),
        (date(2026, 5, 1), date(2026, 5, 31)),
    )
    attendu = (2486.41 + 2478.44 + PLAFOND_MENSUEL_MAI_2026) / 91.25
    assert ijss["base_plafonnee"] == pytest.approx(attendu, abs=0.0001)
    assert ijss["ijss_journaliere"] == pytest.approx(41.19, abs=0.005)
    # Le total plafonné donnait 41,95 €.
    assert _ancienne_base_plafonnee(bruts, PLAFOND_MENSUEL_MAI_2026) / 2 == pytest.approx(
        41.95, abs=0.005
    )
    # Le salaire journalier de base affiché reste celui des bruts réels.
    assert ijss["salaire_journalier_base"] == pytest.approx(sum(bruts) / 91.25, abs=0.0001)


def test_aucune_paie_au_dessus_du_plafond_inchange():
    bruts = [2432.78, 2327.64, 2089.06]
    ijss = _ijss(
        _arret("2026-05-04", "2026-05-31", bruts),
        (date(2026, 5, 1), date(2026, 5, 31)),
    )
    assert ijss["base_plafonnee"] == pytest.approx(
        _ancienne_base_plafonnee(bruts, PLAFOND_MENSUEL_MAI_2026), abs=0.0001
    )
    assert ijss["base_plafonnee"] == pytest.approx(sum(bruts) / 91.25, abs=0.0001)


def test_les_trois_paies_au_dessus_du_plafond_inchange():
    bruts = [2900.0, 3500.0, 5000.0]
    ijss = _ijss(
        _arret("2026-05-04", "2026-05-31", bruts),
        (date(2026, 5, 1), date(2026, 5, 31)),
    )
    assert ijss["base_plafonnee"] == pytest.approx(
        _ancienne_base_plafonnee(bruts, PLAFOND_MENSUEL_MAI_2026), abs=0.0001
    )
    assert ijss["ijss_journaliere"] == pytest.approx(41.95, abs=0.005)


def test_mois_sans_bulletin_le_salaire_de_base_est_plafonne_aussi():
    # Le salaire de base qui remplace un bulletin manquant est une paie
    # estimée : il est retenu dans la même limite.
    ijss = _ijss(
        _arret("2026-05-04", "2026-05-31", [None, 2000.0, 2000.0]),
        (date(2026, 5, 1), date(2026, 5, 31)),
        salaire_base=4000.0,
    )
    attendu = (PLAFOND_MENSUEL_MAI_2026 + 2000.0 + 2000.0) / 91.25
    assert ijss["base_plafonnee"] == pytest.approx(attendu, abs=0.0001)


def test_arret_d_avant_le_1er_avril_2025_garde_l_ancienne_regle():
    # Avant le 01/04/2025 : pas de plafond Smic par paie, l'ancien plafond
    # journalier (1,8 × PSS ÷ 365) porte sur le salaire journalier de base.
    bruts = [9000.0, 1000.0, 1000.0]
    ijss = _ijss(
        _arret("2025-03-10", "2025-03-31", bruts),
        (date(2025, 3, 1), date(2025, 3, 31)),
    )
    assert ijss["base_plafonnee"] == pytest.approx(
        min(sum(bruts) / 91.25, 48060.0 / 365 * 1.8), abs=0.0001
    )
