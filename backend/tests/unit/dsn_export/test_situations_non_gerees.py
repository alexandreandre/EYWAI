"""Ce que la DSN ne sait pas déclarer est dit (R-455, R-456, R-457, R-461, R-471)."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.dsn_export.domain import situations_non_gerees as s
from app.modules.dsn_export.domain.fctu import avis_mois_precedent

pytestmark = pytest.mark.unit


def _sans_solde():
    return {
        "calcul_du_brut": [
            {
                "libelle": "Absence sans solde (01/03 au 31/03)",
                "perte": 500.0,
                "date_debut": "2026-03-01",
                "date_fin": "2026-03-31",
            }
        ]
    }


def test_un_conge_sans_solde_rappelle_les_motifs_que_martine_ne_sait_pas(monkeypatch):
    monkeypatch.setattr(
        s,
        "suspensions_du_bulletin",
        lambda _p: [(s.MOTIF_CONGE_NON_REMUNERE, date(2026, 3, 1), date(2026, 3, 31))],
    )
    alertes = s.avertissements_du_bulletin(_sans_solde(), "1770175123456")
    assert len(alertes) == 1 and "632" in alertes[0] and "650" in alertes[0]


def test_sans_conge_sans_solde_rien(monkeypatch):
    monkeypatch.setattr(s, "suspensions_du_bulletin", lambda _p: [])
    assert s.avertissements_du_bulletin({}, "") == []


def test_participation_d_un_ancien_salarie_est_signalee(monkeypatch):
    monkeypatch.setattr(s, "suspensions_du_bulletin", lambda _p: [])
    alertes = s.avertissements_du_bulletin({"bulletin_kind": "regularisation_participation"}, "x")
    assert len(alertes) == 1 and "2.1.3.6" in alertes[0] and "contrat d'un jour" in alertes[0]


@pytest.mark.parametrize("periode,attendu", [("2027-04", True), ("2027-03", False)])
def test_le_solde_annuel_urssaf_est_rappele_en_avril(periode, attendu):
    assert bool(s.avertissement_cotisations_hors_bulletin(periode)) is attendu


def test_le_fichier_dit_que_les_employeurs_multiples_ne_sont_pas_geres():
    assert "plafond réparti" in s.AVERTISSEMENT_EMPLOYEURS_MULTIPLES


def test_avis_fctu_tant_que_la_dsn_du_mois_d_avant_peut_manquer():
    # Sortie le 03/11, moins de 50 salariés : DSN d'octobre due le 15/11.
    assert "10/2026" in avis_mois_precedent(date(2026, 11, 3), date(2026, 11, 10), 20)
    assert avis_mois_precedent(date(2026, 11, 3), date(2026, 11, 16), 20) is None
