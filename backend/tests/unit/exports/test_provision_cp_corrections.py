"""Provision des congés : les corrections du 03/11/2026 (retour d'Elsa, MAJI mai 2026).

1. Unité : un solde déjà en jours ouvrés n'est pas redivisé par 1,2 (MAJI 30/09 : 20,50 et
   8,32 jours chez Quadra, la provision lisait 17,08 et 6,93).
2. Salariés : ceux présents à la fin du mois demandé, pas ceux actifs aujourd'hui.
3. Charges : un bulletin repris de Quadra porte son total patronal dans `structure_cotisations`.
4. Reprise : avant le mois de la reprise, Martine n'a pas les soldes de Quadra ; après, si.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.exports.domain import provision_cp as domaine
from app.modules.exports.infrastructure import export_provision_cp as module
from app.shared.reprise_paie import Bascule

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def sans_repos(monkeypatch):
    """Le repos compensateur se lit en base : ici, aucun crédit ni repos pris."""
    monkeypatch.setattr(module, "_lire_repos", lambda *a, **k: {})


# --- 1. unité ---------------------------------------------------------------------------------

def test_un_solde_en_jours_ouvres_n_est_pas_converti():
    assert domaine.en_jours_ouvres(20.5, "ouvre", 1.2) == 20.5


def test_un_solde_en_jours_ouvrables_est_converti():
    assert domaine.en_jours_ouvres(30.0, "ouvrable", 1.2) == 25.0


# --- 2. présents à la date ----------------------------------------------------------------------

def test_entre_apres_la_date_n_est_pas_present():
    assert not domaine.present_a_la_date(date(2026, 8, 27), [], date(2026, 5, 31))


def test_sorti_apres_la_date_est_present():
    assert domaine.present_a_la_date(date(2024, 1, 1), [date(2026, 6, 21)], date(2026, 5, 31))


def test_sorti_le_jour_meme_ou_avant_n_est_pas_present():
    assert not domaine.present_a_la_date(date(2024, 1, 1), [date(2026, 5, 31)], date(2026, 5, 31))
    assert not domaine.present_a_la_date(date(2024, 1, 1), [date(2026, 4, 30)], date(2026, 5, 31))


def test_une_sortie_d_un_contrat_d_avant_la_reembauche_ne_compte_pas():
    assert domaine.present_a_la_date(date(2026, 6, 29), [date(2026, 3, 31)], date(2026, 9, 30))


# --- 3. charges d'un bulletin repris ------------------------------------------------------------

def test_le_patronal_d_un_bulletin_martine_vient_des_cotisations_officielles():
    donnees = {"cotisations_officielles": [{"total_patronal": 600.0}, {"total_patronal": 14.53}],
               "structure_cotisations": {"total_patronal": 999.0}}
    assert domaine.patronal_du_bulletin(donnees) == 614.53


def test_le_patronal_d_un_bulletin_repris_vient_de_sa_structure():
    assert domaine.patronal_du_bulletin({"structure_cotisations": {"total_patronal": 614.53}}) == 614.53


def test_un_bulletin_sans_cotisations_a_zero():
    assert domaine.patronal_du_bulletin({}) == 0.0


# --- 4. la reprise ------------------------------------------------------------------------------

SALARIE = {"id": "e1", "matricule": "M", "first_name": "A", "last_name": "B", "hire_date": "2020-01-01",
           "employment_status": "actif", "salaire_de_base": {"valeur": 3000.0}}


def _lecture(bascule):
    return (
        patch.object(module, "_lire_salaries", return_value=[SALARIE]),
        patch.object(module, "_lire_bulletins", return_value={"e1": {(2026, 9): (3000.0, 900.0)}}),
        patch.object(module, "_lire_soldes_ouvres", return_value=(20.5, 8.32)),
        patch.object(module, "_lire_bascule", return_value=bascule),
    )


def test_un_mois_avant_la_reprise_est_bloque():
    a, b, c, d = _lecture(Bascule(annee=2026, mois=9))
    with a, b, c, d:
        apercu = module.preview_provision_cp("c", "2026-05")
    assert apercu["can_generate"] is False
    assert any("09/2026" in x["message"] and x["severity"] == "blocking" for x in apercu["anomalies"])


def test_le_mois_de_la_reprise_se_calcule_sans_l_avertissement_des_soldes_recalcules():
    a, b, c, d = _lecture(Bascule(annee=2026, mois=9))
    with a, b, c, d:
        apercu = module.preview_provision_cp("c", "2026-09")
    assert apercu["can_generate"] is True
    assert not any("recalculé" in w for w in apercu["warnings"])


def test_sans_reprise_ni_bulletin_la_provision_est_bloquee():
    """Cartol, LEWIS, Mont Blanc (03/11) : Quadra fait la paie, Martine n'a ni soldes ni charges."""
    with patch.object(module, "_lire_salaries", return_value=[SALARIE]), \
         patch.object(module, "_lire_bulletins", return_value={}), \
         patch.object(module, "_lire_soldes_ouvres", return_value=(25.0, 8.32)), \
         patch.object(module, "_lire_bascule", return_value=None):
        apercu = module.preview_provision_cp("c", "2026-09")
    assert apercu["can_generate"] is False
    assert any("aucun bulletin" in x["message"] and x["severity"] == "blocking" for x in apercu["anomalies"])


# --- 6. mois d'entrée incomplet ------------------------------------------------------------------

def test_le_mois_d_entree_incomplet_ne_fait_pas_le_salaire_de_reference():
    ref = domaine.reference_du_salarie(
        {(2026, 9): (172.34, 7.64)}, [(2026, m) for m in range(1, 10)], 320.06, date(2026, 9, 9)
    )
    assert ref.salaire_reference == 320.06
    assert ref.taux_charges == 4.43
    assert "premier mois incomplet" in ref.anomalie


def test_entre_le_premier_du_mois_ce_mois_compte():
    ref = domaine.reference_du_salarie(
        {(2026, 9): (1250.90, 30.0)}, [(2026, m) for m in range(1, 10)], 1250.90, date(2026, 9, 1)
    )
    assert ref.salaire_reference == 1250.90
    assert ref.anomalie == ""


def test_le_mois_d_entree_incomplet_est_ecarte_quand_d_autres_mois_existent():
    ref = domaine.reference_du_salarie(
        {(2026, 8): (900.0, 90.0), (2026, 9): (2000.0, 200.0), (2026, 10): (2000.0, 200.0)},
        [(2026, 8), (2026, 9), (2026, 10)], 2000.0, date(2026, 8, 20),
    )
    assert ref.salaire_reference == 2000.0
    assert ref.mois_retenus == "2/3"


def test_sans_reprise_l_avertissement_des_soldes_recalcules_reste():
    a, b, c, d = _lecture(None)
    with a, b, c, d:
        apercu = module.preview_provision_cp("c", "2026-09")
    assert any("recalculé" in w for w in apercu["warnings"])
