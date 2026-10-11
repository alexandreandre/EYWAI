"""Le reçu, l'attestation France Travail et la DSN lisent l'indemnité
compensatrice de congés versée par le bulletin.

Le moteur range cette indemnité dans `details_conges` (son libellé dit « congés
payés »). Le reçu (`lignes_du_bulletin`), l'attestation (`sommes_de_rupture_du_bulletin`)
et le bloc 52 de la DSN (`indemnites_de_rupture`) ne lisaient que `calcul_du_brut`
et le récapitulatif `indemnites_sortie` : fin de CDD de septembre 2026 rejouée
(enquête H, [H8]), ICCP payée 164,04, sommes de rupture = précarité 149,12 seule,
DSN `[('011', 149.12)]` sans code 020 ; démission, DSN 020 au montant du dossier
(2 337,29) au lieu du montant versé (2 867,77).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.dsn_export.domain.evenements import indemnites_de_rupture
from app.modules.payroll.documents.attestation_employeur_salary_history import get_salary_history
from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
    lignes_du_bulletin,
    sommes_de_rupture_du_bulletin,
)

pytestmark = pytest.mark.unit

# Fin de CDD calculée par le moteur (entrée le 24/08, sortie le 11/09).
FIN_CDD = {
    "salaire_brut": 1204.31,
    "net_a_payer": 927.69,
    "calcul_du_brut": [
        {"libelle": "Salaire de base", "quantite": 63.35, "taux": 12.3107, "gain": 779.88},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 7.23, "taux": 15.3884, "gain": 111.27},
        {"libelle": "Prime de précarité (CDD)", "quantite": None, "taux": 0.1, "gain": 149.12},
    ],
    "details_conges": [
        {"libelle": "Indemnité compensatrice de congés payés (CDD)", "quantite": None, "taux": 0.1, "gain": 164.04},
    ],
    "details_absences": [],
    "primes_non_soumises": [],
}

# Démission d'un CDI : congés du mois pris et payés, plus l'indemnité de départ.
DEMISSION = {
    "salaire_brut": 6036.04,
    "net_a_payer": 4899.51,
    "calcul_du_brut": [
        {"libelle": "Salaire de base", "quantite": 151.67, "taux": 15.6560, "gain": 2374.55},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 19.57, "gain": 339.15},
        {"libelle": "Prime d'ancienneté", "gain": 454.57},
    ],
    "details_conges": [
        {"libelle": "Absence congés payés du 07/09/26 au 08/09/26", "quantite": 14, "taux": 15.656, "perte": 219.18},
        {"libelle": "Indemnité de congés payés (maintien de salaire)", "quantite": 14, "taux": 15.656, "gain": 219.18},
        {"libelle": "Indemnité compensatrice de congés payés", "quantite": None, "taux": None, "gain": 2867.77},
    ],
    "details_absences": [],
    "primes_non_soumises": [],
    # Récapitulatif d'un bulletin enregistré avant la correction : le montant
    # du dossier, « intégré au brut », qui n'est pas celui versé.
    "indemnites_sortie": {
        "lignes_soumises": [
            {"libelle": "Indemnité compensatrice de congés payés", "gain": 2337.29, "integree_au_brut": True}
        ],
        "lignes_exonerees": [],
    },
}


def test_le_recu_porte_l_indemnite_de_conges_de_fin_de_cdd():
    remuneration, rupture, _apres = lignes_du_bulletin(FIN_CDD)
    assert [(l["label"], l["montant"]) for l in rupture] == [
        ("Prime de précarité (CDD)", 149.12),
        ("Indemnité compensatrice de congés payés (CDD)", 164.04),
    ]
    assert round(sum(l["montant"] for l in remuneration + rupture), 2) == 1204.31


def test_le_recu_ne_prend_pas_les_conges_du_mois_pour_une_somme_de_rupture():
    _remuneration, rupture, _apres = lignes_du_bulletin(DEMISSION)
    assert [(l["label"], l["montant"]) for l in rupture] == [
        ("Indemnité compensatrice de congés payés", 2867.77)
    ]


def test_l_attestation_declare_l_indemnite_de_conges_versee():
    assert sommes_de_rupture_du_bulletin(FIN_CDD) == [
        {"libelle": "Prime de précarité (CDD)", "montant": 149.12, "dans_le_brut": True},
        {"libelle": "Indemnité compensatrice de congés payés (CDD)", "montant": 164.04, "dans_le_brut": True},
    ]
    assert sommes_de_rupture_du_bulletin(DEMISSION) == [
        {"libelle": "Indemnité compensatrice de congés payés", "montant": 2867.77, "dans_le_brut": True},
    ]


def test_l_attestation_sort_l_indemnite_de_conges_du_salaire_du_mois():
    client = MagicMock()

    class Requete:
        def __getattr__(self, _nom):
            return lambda *a, **k: self

        def execute(self):
            return MagicMock(data=[{"year": 2026, "month": 9, "payslip_data": FIN_CDD}])

    client.table.side_effect = lambda _nom: Requete()
    salarie = {"id": "emp-cdd", "hire_date": "2026-08-24", "contract_type": "CDD",
               "salaire_de_base": {"valeur": 1801.80}, "duree_hebdomadaire": 39}
    historique = get_salary_history("emp-cdd", salarie, "2026-09-11", supabase_client=client)
    septembre = historique["months"][-1]
    assert septembre["gross_salary"] == round(1204.31 - 149.12 - 164.04, 2)


def test_la_dsn_declare_l_indemnite_de_conges_en_020():
    assert indemnites_de_rupture(FIN_CDD, sortie=True) == [
        ("011", 149.12, True),
        ("020", 164.04, True),
    ]


def test_la_dsn_declare_le_montant_verse_et_non_celui_du_dossier():
    assert indemnites_de_rupture(DEMISSION, sortie=True) == [("020", 2867.77, True)]
