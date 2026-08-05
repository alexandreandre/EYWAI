"""Refus d'export d'une OD déséquilibrée.

Un fichier d'écritures déséquilibré est rejeté par tout logiciel comptable.
Mieux vaut un message actionnable qu'un export silencieusement faux.
"""

import pytest

from app.modules.exports.infrastructure.payroll_ledger import (
    LedgerImbalanceError,
    assert_ledger_balanced,
)

pytestmark = pytest.mark.unit


class TestRefusExportDesequilibre:
    def test_od_equilibree_passe(self):
        assert_ledger_balanced({"equilibre": True, "ecart": 0.0, "anomalies": []})

    def test_od_desequilibree_leve_une_erreur_explicite(self):
        with pytest.raises(LedgerImbalanceError) as exc:
            assert_ledger_balanced(
                {
                    "equilibre": False,
                    "ecart": 437.53,
                    "anomalies": [
                        {
                            "code": "element_hors_brut_non_mappe",
                            "label": "Élément hors brut sans compte comptable",
                            "detail": "panier — Paniers jours non soumis",
                            "montant": 606.8,
                        }
                    ],
                }
            )
        message = str(exc.value)
        assert "437.53" in message
        assert "Paniers jours non soumis" in message
        assert "Comptes comptables" in message

    def test_message_sans_anomalie_reste_actionnable(self):
        """Un déséquilibre sans élément non mappé existe : il faut quand même
        dire quoi regarder."""
        with pytest.raises(LedgerImbalanceError) as exc:
            assert_ledger_balanced({"equilibre": False, "ecart": 12.0, "anomalies": []})
        message = str(exc.value)
        assert "12.0" in message
        assert "équilibre" in message.lower()

    def test_anomalies_toutes_listees(self):
        with pytest.raises(LedgerImbalanceError) as exc:
            assert_ledger_balanced(
                {
                    "equilibre": False,
                    "ecart": 1000.0,
                    "anomalies": [
                        {"detail": "cantine — Cantine", "montant": 351.0},
                        {"detail": "ijss — IJSS nettes (rappel)", "montant": 348.83},
                    ],
                }
            )
        message = str(exc.value)
        assert "Cantine" in message
        assert "IJSS" in message


class TestReponseHttp:
    def test_desequilibre_rendu_en_422_avec_son_message(self):
        """L'écran doit pouvoir afficher la liste des comptes à renseigner,
        pas une erreur générique."""
        from app.modules.exports.api.router import _value_error_to_http

        erreur = LedgerImbalanceError(
            "L'écriture ne s'équilibre pas : écart de 606.8 €.\n"
            "  — panier — Paniers jours non soumis (606.8 €)"
        )
        http = _value_error_to_http(erreur)
        assert http.status_code == 422
        assert "Paniers jours non soumis" in http.detail

    def test_autres_value_errors_inchangees(self):
        from app.modules.exports.api.router import _value_error_to_http

        assert _value_error_to_http(ValueError("Bulletin non trouvé")).status_code == 404
        assert _value_error_to_http(ValueError("période invalide")).status_code == 400
