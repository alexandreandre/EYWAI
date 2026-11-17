"""Ce que l'aperçu DSN signale sur une fiche sans bloquer (Lyon, 17/11/2026)."""

import pytest

from app.modules.dsn_export.domain.fiche_a_completer import (
    avertissements_de_la_fiche,
    statut_dsn_contredit_la_fiche,
)
from app.modules.exports.domain.rules import validate_dsn_can_generate


def _fiche(statut, code=None, pcs="388a"):
    return {"statut": statut, "classification_conventionnelle": {"code_statut_dsn": code, "pcs": pcs}}


def test_fiche_cadre_et_dsn_non_cadre():
    assert "non-cadre" in statut_dsn_contredit_la_fiche(_fiche("Cadre", "06"))
    assert statut_dsn_contredit_la_fiche(_fiche("Non-Cadre", "06")) is None
    # 05 + fiche cadre : extension cadre, déclarée cadre.
    assert statut_dsn_contredit_la_fiche(_fiche("Cadre", "05")) is None
    assert statut_dsn_contredit_la_fiche(_fiche("Cadre")) is None


def test_pcs_9999_est_un_code_a_completer():
    assert avertissements_de_la_fiche(_fiche("Non-Cadre", "06", "9999")) == [
        "Code PCS-ESE « 9999 » (S21.G00.40.004) : code à compléter sur la fiche"
    ]
    assert avertissements_de_la_fiche(_fiche("Non-Cadre", "06")) == []


def test_un_avertissement_de_fiche_se_fait_accepter_comme_les_autres():
    apercu = {
        "anomalies": [{"severity": "warning", "code": "a_voir_sur_la_fiche", "message": "x"}],
        "warnings": [],
    }
    with pytest.raises(ValueError):
        validate_dsn_can_generate(apercu, accept_warnings=False)
    validate_dsn_can_generate(apercu, accept_warnings=True)
