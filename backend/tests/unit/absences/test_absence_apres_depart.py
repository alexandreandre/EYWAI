"""Absence d'un salarié dont le départ est créé.

Un déclencheur en base refusait toute demande dès qu'un départ existait, même
pour un jour avant le dernier jour travaillé, et l'écran affichait l'erreur
Postgres brute en 500 (02/10/2026, salariée en fin de CDD). Le déclencheur ne
refuse plus que les jours après le dernier jour travaillé, et ce refus arrive
à l'écran en 400 avec sa phrase.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
_FICHE = "cccccccc-3333-3333-3333-333333333333"
_MIGRATIONS = Path(__file__).resolve().parents[4] / "supabase" / "migrations"


def _rh() -> User:
    return User(
        id="dddddddd-4444-4444-4444-444444444444", email="rh@societe-a.fr",
        first_name="Rita", last_name="Aitch", is_platform_admin=False, is_group_admin=False,
        accessible_companies=[CompanyAccess(company_id=_SOCIETE, company_name="Société A", role="rh", is_primary=True)],
        active_company_id=_SOCIETE,
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = _rh
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_le_refus_du_declencheur_arrive_en_400_avec_sa_phrase(client):
    refus = APIError({
        "code": "23514",
        "message": "Impossible de créer une demande d'absence après le dernier jour travaillé (15/10/2026).",
        "details": None, "hint": None,
    })
    with patch("app.modules.absences.api.router._resolve_create_absence_employee_id", return_value=_FICHE), patch(
        "app.modules.absences.api.router.commands.create_absence_request", side_effect=refus
    ):
        reponse = client.post(
            "/api/absences/requests",
            json={"employee_id": _FICHE, "type": "conge_paye", "selected_days": ["2026-10-20"]},
        )
    assert reponse.status_code == 400
    assert reponse.json()["detail"] == (
        "Impossible de créer une demande d'absence après le dernier jour travaillé (15/10/2026)."
    )


def test_le_declencheur_ne_refuse_que_les_jours_apres_le_dernier_jour_travaille():
    candidats = sorted(_MIGRATIONS.glob("*_absence_apres_depart.sql"))
    assert len(candidats) == 1, candidats
    sql = candidats[0].read_text(encoding="utf-8")
    assert "CREATE OR REPLACE FUNCTION public.check_employee_exit_status_before_absence()" in sql
    assert "unnest(NEW.selected_days)" in sql
    assert "> v_dernier_jour" in sql
    assert "après le dernier jour travaillé" in sql
