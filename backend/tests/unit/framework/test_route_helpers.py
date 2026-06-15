"""Tests du helper de collecte des routes FastAPI."""

from app.main import app
from tests.route_helpers import collect_app_route_paths


def test_collect_app_route_paths_includes_bonus_types_and_planning() -> None:
    paths = collect_app_route_paths(app)
    assert any("/api/bonus-types" in p for p in paths)
    assert any("/api/planning" in p for p in paths)
