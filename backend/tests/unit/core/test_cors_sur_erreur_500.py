"""Une erreur 500 non rattrapée garde ses en-têtes CORS.

Le gestionnaire des exceptions générales tourne hors du middleware CORS : sa
réponse partait sans Access-Control-Allow-Origin, et le navigateur la changeait
en « erreur réseau » (recette du 02/10/2026 : « délai dépassé ou surcharge
serveur » au lieu de l'erreur du serveur).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

_CHEMIN = "/__test_erreur_500"


@pytest.fixture
def client():
    def boum():
        raise RuntimeError("panne simulée")

    app.add_api_route(_CHEMIN, boum, methods=["GET"])
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != _CHEMIN]


def test_une_origine_autorisee_recoit_les_en_tetes_cors(client):
    reponse = client.get(_CHEMIN, headers={"Origin": "http://localhost:5173"})
    assert reponse.status_code == 500
    assert reponse.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert reponse.headers.get("access-control-allow-credentials") == "true"


def test_une_origine_inconnue_ne_recoit_rien(client):
    reponse = client.get(_CHEMIN, headers={"Origin": "https://inconnu.example"})
    assert reponse.status_code == 500
    assert "access-control-allow-origin" not in reponse.headers
