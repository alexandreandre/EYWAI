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


@pytest.fixture(autouse=True)
def bulletins_valides_et_a_jour(monkeypatch):
    """L'aperçu ne lit pas l'état des bulletins en base : tous validés et à jour."""
    monkeypatch.setattr(
        "app.modules.exports.application.queries.lire_etat_bulletins",
        lambda *args, **kwargs: (0, 0, 0),
    )
