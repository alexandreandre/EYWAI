"""L'aperçu du virement des salaires dit « sans BIC » et « transmission manuelle ».

Ces deux avertissements n'existaient que dans `preview_sepa`, que plus aucun
écran n'appelle : l'aperçu réel (`preview_paiement_salaires`) ne les disait pas.
"""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_paiement_salaires as salaires

pytestmark = pytest.mark.unit

IBAN = "FR7630001007941234567890185"


def _ligne(bic):
    return {
        "Nom": "Dupont",
        "Prénom": "Jean",
        "IBAN": IBAN,
        "BIC": bic,
        "Montant": 1800.0,
        "Statut_controle": "OK",
    }


def _apercu(rows, **kwargs):
    totals = {"virements_count": len(rows), "total_amount": 1800.0 * len(rows)}
    with patch.object(salaires, "get_paiement_salaires_data", return_value=(rows, totals, [], [])):
        return salaires.preview_paiement_salaires("co-1", "2026-09", **kwargs)


def test_signale_les_salaries_sans_bic_sans_bloquer():
    apercu = _apercu([_ligne(""), _ligne("BNPAFRPP")])
    assert any("1 salarié sans BIC" in w and "reste valide" in w for w in apercu["warnings"])
    assert apercu["can_generate"] is True


def test_silencieux_quand_tous_les_bic_sont_presents():
    apercu = _apercu([_ligne("BNPAFRPP")])
    assert not any("sans BIC" in w for w in apercu["warnings"])


def test_dit_que_la_transmission_est_manuelle():
    apercu = _apercu([_ligne("BNPAFRPP")])
    assert "Format SEPA pain.001.001.03 — transmission manuelle à la banque." in apercu["warnings"]


def test_un_fichier_csv_n_est_pas_presente_comme_du_sepa():
    apercu = _apercu([_ligne("")], bank_format="csv")
    assert "Fichier CSV — transmission manuelle à la banque." in apercu["warnings"]
    assert not any("SEPA" in w for w in apercu["warnings"])
    assert not any("sans BIC" in w for w in apercu["warnings"])
