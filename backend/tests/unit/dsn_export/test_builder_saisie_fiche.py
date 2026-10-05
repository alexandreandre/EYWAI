"""Motif de recours et niveau de diplôme saisis sur la fiche.

L'écran les range sous `specificites_paie.dsn_reprise`, là où le chargeur de
reprise pose ceux des salariés repris : le builder doit les y lire.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.application.builder import build_individu_from_payroll

pytestmark = pytest.mark.unit

SALARIE = {
    "id": "n1",
    "first_name": "Lucie",
    "last_name": "IMAGINAIRE",
    "nir": "290017512345678",
    "sexe": "F",
    "date_naissance": "1990-01-15",
    "lieu_naissance": "LYON (69)",
    "adresse": {"rue": "2 rue Inventée", "ville": "LYON", "code_postal": "69002"},
    "hire_date": "2026-09-01",
    "contract_type": "CDD",
    "contract_end_date": "2027-02-28",
    "statut": "Non-Cadre",
    "duree_hebdomadaire": 35.0,
    "classification_conventionnelle": {"pcs": "674a", "idcc": "0292"},
}


def _construire(salarie):
    return build_individu_from_payroll(
        salarie,
        {"salaire_brut": 2000.0, "synthese_net": {"net_imposable": 1600.0}},
        period="2026-10",
        company_siret="80248516900022",
    )


def test_le_motif_de_recours_de_la_fiche_est_declare():
    salarie = {**SALARIE, "specificites_paie": {"dsn_reprise": {"motif_recours": "02"}}}
    individu, _ = _construire(salarie)
    assert individu.contrats[0].rubriques["S21.G00.40.021"] == "02"


def test_le_niveau_de_diplome_de_la_fiche_est_declare():
    salarie = {
        **SALARIE,
        "contract_type": "Apprentissage",
        "specificites_paie": {"dsn_reprise": {"niveau_diplome_prepare": "05"}},
    }
    individu, _ = _construire(salarie)
    assert individu.rubriques["S21.G00.30.025"] == "05"


def test_sans_motif_rien_n_est_invente():
    individu, _ = _construire(SALARIE)
    assert "S21.G00.40.021" not in individu.contrats[0].rubriques
