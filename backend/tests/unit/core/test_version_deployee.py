"""La version du code en ligne se lit dans /health (support : quel code a calculé un bulletin)."""

from fastapi.testclient import TestClient

from app.core import settings
from app.main import app


def test_health_dit_la_version_et_le_commit(monkeypatch):
    monkeypatch.setattr(settings, "MARTINE_VERSION", "paie-2026-11-03.1")
    monkeypatch.setattr(settings, "MARTINE_COMMIT", "0123456789abcdef")
    rep = TestClient(app).get("/health")
    assert rep.status_code == 200
    assert rep.json() == {"status": "ok", "version": "paie-2026-11-03.1", "commit": "0123456789abcdef"}


def test_une_image_non_etiquetee_le_dit(monkeypatch):
    monkeypatch.setattr(settings, "MARTINE_VERSION", None)
    monkeypatch.setattr(settings, "MARTINE_COMMIT", None)
    corps = TestClient(app).get("/health").json()
    assert corps == {"status": "ok", "version": None, "commit": None}
