"""Après l'enregistrement, la route répond avec la ligne enrichie : l'enrichissement ne doit plus
appeler l'attestation de salaire retirée, sinon la saisie répond 500 alors que l'absence est écrite."""
from app.modules.absences.api import router as module_router


def test_ligne_saisie_rendue_sans_attestation(monkeypatch):
    vus = []
    monkeypatch.setattr(module_router.queries, "_enrich_with_signed_urls", vus.append)
    ligne = {"id": "a1", "type": "arret_maladie", "employee": {"id": "e1"}}

    rendu = module_router._enrich_single_absence_row(ligne)

    assert rendu == {"id": "a1", "type": "arret_maladie"}
    assert vus == [[rendu]]


def test_ligne_a_valider_garde_le_salarie(monkeypatch):
    monkeypatch.setattr(module_router.queries, "_enrich_with_signed_urls", lambda lignes: None)

    rendu = module_router._enrich_absence_row_keep_employee({"id": "a1", "employee": [{"id": "e1"}]})

    assert rendu["employee"] == {"id": "e1"}
