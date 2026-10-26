"""Un arrêt tout entier dans la carence n'a pas d'IJSS : ce n'est pas une alerte.

Un arrêt maladie de trois jours tombe dans la carence de la Sécurité sociale :
aucune IJSS n'est due, 0 € est la bonne réponse. Avant le 26/10/2026, une
subrogation demandée et 0 € d'IJSS déclenchaient « IJSS non calculables,
vérifier le salaire journalier de base » (MAJI, arrêt du 20 au 22/10/2026),
alerte fausse sur tous les arrêts courts. L'alerte reste quand des jours sont
indemnisables et que le montant tombe à 0.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .test_maintien_sans_subrogation import JUIN, _arret, _ctx, _legal

pytestmark = pytest.mark.unit


def _alertes(**arret):
    r = calculer_maintien(_arret(subrogation_active=True, **arret), _ctx(), _legal(), *JUIN)
    return r["ijss"], [a for a in r.get("alertes") or [] if "IJSS non calculables" in a]


def test_un_arret_de_trois_jours_dans_la_carence_ne_declenche_pas_d_alerte():
    ijss, alertes = _alertes(date_debut="2025-06-10", date_fin="2025-06-12")
    assert ijss["nb_jours_indemnises"] == 0
    assert ijss["ijss_theorique"] == 0.0
    assert alertes == []


def test_sans_salaire_de_base_l_alerte_reste_quand_des_jours_sont_indemnisables():
    r = calculer_maintien(
        _arret(subrogation_active=True), type(_ctx())(**{**vars(_ctx()), "salaire_base_mensuel": 0.0}),
        _legal(), *JUIN,
    )
    assert r["ijss"]["nb_jours_indemnises"] > 0
    assert any("IJSS non calculables" in a for a in r.get("alertes") or [])
