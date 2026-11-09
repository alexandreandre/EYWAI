"""Limite de débit des surfaces publiques (R-668)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException, Request

from app.core import limite_debit
from tests.unit.security.test_routes_authentifiees import (
    ROUTES_PUBLIQUES_ASSUMEES,
    _routes_terminales,
)

# Répond is_test et une date : aucune donnée, aucun essai à freiner.
SANS_LIMITE = {("GET", "/api/test-env/status")}


def _requete(adresse: str = "10.0.0.1") -> Request:
    return Request({"type": "http", "client": (adresse, 1234), "headers": []})


@pytest.fixture(autouse=True)
def _table_vide():
    limite_debit._essais.clear()
    yield
    limite_debit._essais.clear()


def test_au_dela_du_plafond_la_reponse_est_429():
    garde = limite_debit.limite_de_debit("essai", 2)
    garde(_requete())
    garde(_requete())
    with pytest.raises(HTTPException) as exc:
        garde(_requete())
    assert exc.value.status_code == 429


def test_le_compte_est_propre_a_chaque_adresse():
    garde = limite_debit.limite_de_debit("essai", 1)
    garde(_requete("10.0.0.1"))
    garde(_requete("10.0.0.2"))


def test_le_compte_est_propre_a_chaque_surface():
    limite_debit.limite_de_debit("a", 1)(_requete())
    limite_debit.limite_de_debit("b", 1)(_requete())


def test_la_fenetre_expire():
    garde = limite_debit.limite_de_debit("essai", 1)
    with patch.object(limite_debit.time, "monotonic", return_value=1000.0):
        garde(_requete())
    with patch.object(limite_debit.time, "monotonic", return_value=1061.0):
        garde(_requete())


def test_la_memoire_reste_bornee():
    garde = limite_debit.limite_de_debit("essai", 1)
    with patch.object(limite_debit, "MAX_CLES_SUIVIES", 3):
        for i in range(10):
            garde(_requete(f"10.0.1.{i}"))
    assert len(limite_debit._essais) <= 3


def test_toute_route_publique_porte_une_limite():
    sans = []
    for route in _routes_terminales():
        for methode in getattr(route, "methods", None) or set():
            cle = (methode, getattr(route, "path", ""))
            if cle not in ROUTES_PUBLIQUES_ASSUMEES or cle in SANS_LIMITE:
                continue
            noms = {
                getattr(d.call, "__name__", "") for d in route.dependant.dependencies
            }
            if "garde_de_debit" not in noms:
                sans.append(cle)
    assert not sans, f"Route publique sans limite de débit : {sorted(sans)}"
