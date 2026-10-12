"""[B4] Un cadre sans ligne de prévoyance : aucune cotisation, et désormais une alerte.

Pour un non-cadre adhérent sans ligne, le barème national s'applique. Pour un
cadre, le moteur ne pose que les lignes de la fiche : case cochée sans ligne, ou
case décochée, le bulletin ne porte aucune prévoyance. Rejoué le 12/10/2026 sur
un cadre réel de septembre, lignes retirées en mémoire : −79,61 € de coût et
rien ne le disait. L'alerte ne bloque pas : refuser la génération est une
décision à prendre.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

LIGNE = {"id": "prev_ta", "base": "brut_plafonne", "libelle": "Prévoyance cadre TA",
         "salarial": 0.00365, "patronal": 0.01825, "forfait_social": 0.08}


def _alertes(statut, prevoyance):
    ctx = build_test_contexte(
        statut=statut, salaire_base=3500.0, specificites_extra={"prevoyance": prevoyance}
    )
    ctx.month = 9
    lignes, _ = calculer_cotisations(ctx, 3500.0, 0.0, 0.0)
    return lignes, {a.get("code"): a for a in ctx.alertes_baremes if isinstance(a, dict)}


def test_cadre_adherent_sans_ligne_est_signale():
    lignes, alertes = _alertes("Cadre", {"adhesion": True, "lignes_specifiques": []})
    assert not any(l.get("coti_id") == "prevoyance_cadre" for l in lignes)
    alerte = alertes.get("prevoyance_cadre_sans_ligne")
    assert alerte is not None
    assert "aucune cotisation de prévoyance" in alerte["message"]
    assert "lignes du contrat de prévoyance" in alerte["message"]
    assert alerte["critique"] is False


def test_cadre_sans_adhesion_est_signale():
    _, alertes = _alertes("Cadre", {"adhesion": False, "lignes_specifiques": []})
    alerte = alertes.get("prevoyance_cadre_absente")
    assert alerte is not None
    assert "aucune cotisation de prévoyance" in alerte["message"]
    assert alerte["critique"] is False


def test_cadre_avec_ses_lignes_n_est_pas_signale():
    lignes, alertes = _alertes("Cadre", {"adhesion": True, "lignes_specifiques": [LIGNE]})
    assert any(l.get("libelle") == "Prévoyance cadre TA" for l in lignes)
    assert "prevoyance_cadre_sans_ligne" not in alertes
    assert "prevoyance_cadre_absente" not in alertes


def test_non_cadre_sans_ligne_n_est_pas_signale():
    """Le barème national s'applique : rien à signaler."""
    _, alertes = _alertes("Non-Cadre", {"adhesion": True, "lignes_specifiques": []})
    assert "prevoyance_cadre_sans_ligne" not in alertes
    assert "prevoyance_cadre_absente" not in alertes
