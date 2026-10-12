"""Les tests d'export ne lisent jamais le compte bancaire de la société en base."""

import pytest

COMPTE_SOCIETE_DE_TEST = {
    "iban": "FR1420041010050500013M02606",
    "bic": "BNPAFRPP",
    "titulaire": "SAS Exemple",
}


@pytest.fixture(autouse=True)
def compte_societe_renseigne(monkeypatch):
    """Par défaut la société a un compte ; un test qui veut l'absence le retire."""
    for module in ("export_sepa", "export_paiement_salaires", "export_virement_acomptes"):
        monkeypatch.setattr(
            f"app.modules.exports.infrastructure.{module}.charger_compte_societe",
            lambda company_id: COMPTE_SOCIETE_DE_TEST,
        )
