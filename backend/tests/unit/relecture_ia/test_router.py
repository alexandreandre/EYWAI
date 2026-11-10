"""Les routes, dépendances simulées : ni base ni IA."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.relecture_ia.application import service
from app.modules.relecture_ia.domain.banc import bilan_du_banc

pytestmark = pytest.mark.unit

PREFIXE = "/api/relecture-ia"
AUTORISE = "eandre@maji-invest.fr"


def _utilisateur(email=AUTORISE, rh=True, active="c1"):
    return SimpleNamespace(
        id="u1",
        email=email,
        active_company_id=active,
        accessible_companies=[SimpleNamespace(company_id="c1", company_name="Alpha")],
        has_rh_access_in_company=lambda _c: rh,
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("RELECTURE_IA_COMPTES", raising=False)
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def _connecte(**kwargs):
    app.dependency_overrides[get_current_user] = lambda: _utilisateur(**kwargs)


def test_droits_du_compte_autorise(client):
    _connecte()
    assert client.get(f"{PREFIXE}/droits").json() == {"peut_lancer": True}


def test_droits_d_un_autre_compte(client):
    _connecte(email="autre@exemple.fr")
    assert client.get(f"{PREFIXE}/droits").json() == {"peut_lancer": False}


@pytest.mark.parametrize(
    ("methode", "chemin", "corps"),
    [
        ("get", "/preparation?year=2026&month=10", None),
        ("post", "/lancer", {"year": 2026, "month": 10, "company_ids": ["c1"]}),
        ("get", "/etat", None),
    ],
)
def test_lancer_et_suivre_reserves_au_compte(client, methode, chemin, corps):
    _connecte(email="autre@exemple.fr")
    reponse = getattr(client, methode)(
        PREFIXE + chemin, **({"json": corps} if corps is not None else {})
    )
    assert reponse.status_code == 403
    assert "réservée" in reponse.json()["detail"]


def test_lancer_pose_la_tache_de_fond(client, monkeypatch):
    _connecte()
    executees: list[str] = []
    monkeypatch.setattr(
        service,
        "lancer",
        lambda *a, **k: {"statut": "lancee", "message": None, "relecture_id": "r1", "a_executer": True},
    )
    monkeypatch.setattr(service, "executer", lambda rid, **k: executees.append(rid))
    reponse = client.post(f"{PREFIXE}/lancer", json={"year": 2026, "month": 10, "company_ids": ["c1"]})
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "lancee", "message": None, "relecture_id": "r1"}
    assert executees == ["r1"]


def test_lancer_rien_a_relire_ne_pose_pas_de_tache(client, monkeypatch):
    _connecte()
    monkeypatch.setattr(
        service,
        "lancer",
        lambda *a, **k: {"statut": "rien_a_relire", "message": "Rien.", "relecture_id": None, "a_executer": False},
    )
    monkeypatch.setattr(service, "executer", lambda *a, **k: pytest.fail("ne doit pas tourner"))
    reponse = client.post(f"{PREFIXE}/lancer", json={"year": 2026, "month": 10, "company_ids": ["c1"]})
    assert reponse.json()["statut"] == "rien_a_relire"


@pytest.mark.parametrize(
    ("erreur", "code"),
    [(service.SansSocieteCochee, 400), (service.SocieteRefusee, 403)],
)
def test_lancer_refus_expliques(client, monkeypatch, erreur, code):
    _connecte()

    def lever(*_a, **_k):
        raise erreur

    monkeypatch.setattr(service, "lancer", lever)
    reponse = client.post(f"{PREFIXE}/lancer", json={"year": 2026, "month": 10, "company_ids": ["c1"]})
    assert reponse.status_code == code
    assert reponse.json()["detail"]


def test_mois_invalide_refuse(client):
    _connecte()
    assert client.post(f"{PREFIXE}/lancer", json={"year": 2026, "month": 13, "company_ids": []}).status_code == 422


def test_etat_reprend_une_relecture_bloquee(client, monkeypatch):
    _connecte()
    executees: list[str] = []
    monkeypatch.setattr(service, "lire_etat", lambda: {"relecture": {"id": "r1"}, "a_executer": True})
    monkeypatch.setattr(service, "executer", lambda rid, **k: executees.append(rid))
    assert client.get(f"{PREFIXE}/etat").json() == {"relecture": {"id": "r1"}}
    assert executees == ["r1"]


def test_a_regarder_ouvert_aux_rh_de_la_societe(client, monkeypatch):
    _connecte(email="rh@exemple.fr")
    monkeypatch.setattr(service, "lire_a_regarder", lambda c, y, m: {"societe": c, "points": []})
    assert client.get(f"{PREFIXE}/a-regarder?year=2026&month=10").json() == {"societe": "c1", "points": []}


def test_a_regarder_refuse_sans_acces_rh(client):
    _connecte(email="rh@exemple.fr", rh=False)
    assert client.get(f"{PREFIXE}/a-regarder?year=2026&month=10").status_code == 403


def test_a_regarder_sans_societe_active(client):
    _connecte(active=None)
    assert client.get(f"{PREFIXE}/a-regarder?year=2026&month=10").status_code == 400


def test_marquer_vu(client, monkeypatch):
    _connecte(email="rh@exemple.fr")
    appels: list[tuple] = []
    monkeypatch.setattr(service, "marquer_vu", lambda *a: appels.append(a))
    reponse = client.post(f"{PREFIXE}/vus", json={"bulletin_relu_id": "b1", "ligne": "Brut"})
    assert reponse.status_code == 204
    assert appels == [("c1", "u1", "b1", "Brut")]


def test_marquer_vu_point_introuvable(client, monkeypatch):
    _connecte()

    def lever(*_a):
        raise service.PointIntrouvable

    monkeypatch.setattr(service, "marquer_vu", lever)
    assert client.post(f"{PREFIXE}/vus", json={"bulletin_relu_id": "b1", "ligne": "x"}).status_code == 404


class TestBanc:
    def test_trouves_manques_fausses_alertes(self):
        cas = [
            {"bulletin": "p1", "ligne": "Salaire de base"},
            {"bulletin": "p1", "ligne": "Prime X"},
            {"bulletin": "p2", "ligne": None},
        ]
        resultats = [
            {
                "payslip_id": "p1",
                "signalements": [{"ligne": "SALAIRE de base"}, {"ligne": "Autre"}],
                "cout_usd": 0.05,
            },
            {"payslip_id": "p2", "signalements": [{"ligne": "Brut"}], "cout_usd": 0.05},
        ]
        bilan = bilan_du_banc(cas, resultats)
        assert bilan["trouves"] == [{"bulletin": "p1", "ligne": "salaire de base"}]
        assert bilan["manques"] == [{"bulletin": "p1", "ligne": "prime x"}]
        assert [f["bulletin"] for f in bilan["fausses_alertes"]] == ["p1", "p2"]
        assert bilan["cout_usd"] == 0.1

    def test_echec_compte_manque(self):
        bilan = bilan_du_banc(
            [{"bulletin": "p1", "ligne": "Brut"}],
            [{"payslip_id": "p1", "statut": "echec", "message": "Refus"}],
        )
        assert bilan["manques"] == [{"bulletin": "p1", "ligne": "brut"}]
        assert bilan["echecs"] == [{"bulletin": "p1", "message": "Refus"}]
