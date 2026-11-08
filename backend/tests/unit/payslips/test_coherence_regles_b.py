"""Une erreur que la revue voit bloque la validation, à moins d'être acquittée [R-171]."""

from __future__ import annotations

import pytest

from app.modules.payslips.domain.coherence import raisons_de_ne_pas_valider

pytestmark = pytest.mark.unit


def _bulletin(**autres):
    return {
        "salaire_brut": 2000.0,
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": 2000.0, "perte": None}],
        **autres,
    }


def test_un_bulletin_coherent_se_valide():
    assert raisons_de_ne_pas_valider(_bulletin()) == []


def test_un_ecart_critique_bloque_et_dit_quoi_faire():
    raisons = raisons_de_ne_pas_valider(_bulletin(salaire_brut=2100.0))
    assert len(raisons) == 1
    assert "salaire brut" in raisons[0].lower()
    assert "acquittez" in raisons[0].lower()


def test_un_ecart_acquitte_ne_bloque_plus():
    donnees = _bulletin(salaire_brut=2100.0, alerts_status={"B02": {"status": "acquittee", "by": "rh"}})
    assert raisons_de_ne_pas_valider(donnees) == []


def test_un_bulletin_repris_n_est_pas_bloque():
    assert raisons_de_ne_pas_valider(_bulletin(salaire_brut=2100.0, reprise={"source": "x"})) == []


def test_un_bulletin_sans_lignes_n_est_pas_juge():
    assert raisons_de_ne_pas_valider({"salaire_brut": 1}) == []
