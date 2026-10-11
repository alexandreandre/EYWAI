"""IJSS estimées d'un arrêt maladie : formule et plafond légaux.

Règle (CSS R323-4 ; ameli, « Arrêt de travail pour maladie : les indemnités
journalières du salarié » ; référentiel du dépôt,
docs/audit-maji-2026/referentiel-legal-2026.md, R05) : l'IJ vaut 50 % du
salaire journalier de base, égal aux trois derniers salaires bruts ÷ 91,25,
retenus dans la limite de 1,4 Smic mensuel pour les arrêts depuis le
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
