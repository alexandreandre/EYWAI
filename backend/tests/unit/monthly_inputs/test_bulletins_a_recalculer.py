"""Une saisie créée, corrigée ou supprimée dans un mois qui a déjà un bulletin :
la réponse dit quels bulletins deviennent « À recalculer » (défaut 8 du lot écran)."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.monthly_inputs.application import queries
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE = "11111111-1111-1111-1111-111111111111"
SALARIE = "44444444-4444-4444-4444-444444444444"
SAISIE = "55555555-5555-5555-5555-555555555555"
CIBLE = {"employee_id": SALARIE, "year": 2026, "month": 10}


def _rh() -> User:
    return User(
        id="33333333-3333-3333-3333-333333333333",
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=SOCIETE, company_name="Société", role="rh", is_primary=True)
        ],
        active_company_id=SOCIETE,
    )


def _client() -> TestClient:
    app.dependency_overrides[get_current_user] = _rh
    return TestClient(app)


def _fin():
    app.dependency_overrides.pop(get_current_user, None)


def test_la_requete_ne_garde_que_les_bulletins_calcules_du_mois():
    with patch(
        "app.modules.monthly_inputs.application.queries.monthly_inputs_repository"
    ) as repo:
        repo.employes_avec_bulletin.return_value = [SALARIE]
        trouves = queries.bulletins_a_recalculer(SOCIETE, [(SALARIE, 2026, 10), ("autre", 2026, 10)])
    assert trouves == [CIBLE]
    repo.employes_avec_bulletin.assert_called_once()


def test_sans_bulletin_la_liste_est_vide():
    with patch(
        "app.modules.monthly_inputs.application.queries.monthly_inputs_repository"
    ) as repo:
        repo.employes_avec_bulletin.return_value = []
        assert queries.bulletins_a_recalculer(SOCIETE, [(SALARIE, 2026, 10)]) == []


def test_la_creation_dit_quels_bulletins_sont_a_recalculer():
    try:
        with (
            patch("app.modules.monthly_inputs.api.router.commands") as commands,
            patch(
                "app.modules.monthly_inputs.api.router.queries.bulletins_a_recalculer",
                return_value=[CIBLE],
            ) as q,
        ):
            commands.create_monthly_inputs_batch.return_value.inserted_count = 1
            r = _client().post(
                "/api/monthly-inputs",
                json=[
                    {"employee_id": SALARIE, "year": 2026, "month": 10, "name": "Prime", "amount": 50}
                ],
            )
    finally:
        _fin()
    assert r.status_code == 201
    assert r.json()["bulletins_a_recalculer"] == [CIBLE]
    assert q.call_args.args[1] == [(SALARIE, 2026, 10)]


def test_la_correction_dit_quels_bulletins_sont_a_recalculer():
    try:
        with (
            patch("app.modules.monthly_inputs.api.router.commands") as commands,
            patch(
                "app.modules.monthly_inputs.api.router.queries.bulletins_a_recalculer",
                return_value=[CIBLE],
            ),
        ):
            commands.update_monthly_input.return_value = {
                "id": SAISIE, "employee_id": SALARIE, "year": 2026, "month": 10, "amount": 80,
            }
            r = _client().patch(f"/api/monthly-inputs/{SAISIE}", json={"amount": 80})
    finally:
        _fin()
    assert r.status_code == 200
    assert r.json()["bulletins_a_recalculer"] == [CIBLE]
    assert r.json()["amount"] == 80


def test_la_suppression_dit_quels_bulletins_sont_a_recalculer():
    try:
        with (
            patch("app.modules.monthly_inputs.api.router.commands") as commands,
            patch(
                "app.modules.monthly_inputs.api.router.queries.cible_de_la_saisie",
                return_value=(SALARIE, 2026, 10),
            ),
            patch(
                "app.modules.monthly_inputs.api.router.queries.bulletins_a_recalculer",
                return_value=[CIBLE],
            ),
        ):
            commands.delete_monthly_input.return_value = False
            r = _client().delete(f"/api/monthly-inputs/{SAISIE}")
    finally:
        _fin()
    assert r.status_code == 200
    assert r.json()["bulletins_a_recalculer"] == [CIBLE]


def test_une_recherche_en_echec_ne_perd_pas_l_ecriture():
    """La saisie est enregistrée : si la recherche des bulletins échoue, la réponse
    le dit (null) au lieu d'annoncer une erreur d'enregistrement."""
    try:
        with (
            patch("app.modules.monthly_inputs.api.router.commands") as commands,
            patch(
                "app.modules.monthly_inputs.api.router.queries.bulletins_a_recalculer",
                side_effect=RuntimeError("base injoignable"),
            ),
        ):
            commands.create_monthly_inputs_batch.return_value.inserted_count = 1
            r = _client().post(
                "/api/monthly-inputs",
                json=[
                    {"employee_id": SALARIE, "year": 2026, "month": 10, "name": "Prime", "amount": 50}
                ],
            )
    finally:
        _fin()
    assert r.status_code == 201
    assert r.json()["bulletins_a_recalculer"] is None
