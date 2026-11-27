"""Tests des commandes de bulletin : sans base, les congés parentaux du salarié
(ancienneté de la prévoyance obligatoire, L1225-54) se lisent vides, sauf dans
un test qui les fournit lui-même."""

import pytest


@pytest.fixture(autouse=True)
def _sans_conge_parental_lu_en_base(monkeypatch):
    from app.shared.infrastructure import conge_parental

    monkeypatch.setattr(conge_parental, "conges_parentaux_du_salarie", lambda *_a, **_k: [])
