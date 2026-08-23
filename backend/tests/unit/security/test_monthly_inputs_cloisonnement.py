"""
Comportement HTTP réel des routes fermées le 22/08 (audit sécurité).

Deux invariants, testés par les VRAIS points d'entrée (TestClient sur
app.main.app) :
1. sans jeton → 401/403, jamais de données ;
2. avec jeton → uniquement la société ACTIVE de l'appelant (le client
   Supabase du backend est service_role : sans filtre applicatif, une RH
   verrait la paie des autres clients).
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

SOCIETE_A = "11111111-1111-1111-1111-111111111111"
SOCIETE_B = "22222222-2222-2222-2222-222222222222"
RH_ID = "33333333-3333-3333-3333-333333333333"
SALARIE_ID = "44444444-4444-4444-4444-444444444444"


def _user(role: str = "rh", company_id: str = SOCIETE_A) -> User:
    return User(
        id=RH_ID,
        email="rh@entreprise.fr",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Société A",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)


ROUTES_ANONYMES = [
    ("get", "/api/monthly-inputs?year=2026&month=5", None),
    ("post", "/api/monthly-inputs", []),
    ("patch", f"/api/monthly-inputs/{SALARIE_ID}", {"amount": 1.0}),
    ("delete", f"/api/monthly-inputs/{SALARIE_ID}", None),
    ("get", f"/api/employees/{SALARIE_ID}/monthly-inputs?year=2026&month=5", None),
    (
        "post",
        f"/api/employees/{SALARIE_ID}/monthly-inputs",
        {"year": 2026, "month": 5, "name": "Prime", "amount": 10.0},
    ),
    ("delete", f"/api/employees/{SALARIE_ID}/monthly-inputs/{SALARIE_ID}", None),
    ("get", "/api/primes-catalogue", None),
    ("get", f"/api/absences/employees/{SALARIE_ID}", None),
    (
        "post",
        "/api/saisies-avances/salary-seizures/calculate-seizable",
        {"net_salary": 2000, "dependents_count": 0},
    ),
]


class TestAucunAccesAnonyme:
    def test_les_dix_routes_refusent_l_anonyme(self):
        client = TestClient(app)
        fautives = []
        for methode, url, corps in ROUTES_ANONYMES:
            reponse = getattr(client, methode)(
                url, **({"json": corps} if corps is not None else {})
            )
            if reponse.status_code not in (401, 403):
                fautives.append((methode.upper(), url, reponse.status_code))
        assert not fautives, (
            "Routes accessibles sans authentification : "
            + ", ".join(f"{m} {u} → {c}" for m, u, c in fautives)
        )


class TestCloisonnementSociete:
    def test_la_liste_du_mois_est_filtree_sur_la_societe_active(self):
        app.dependency_overrides[get_current_user] = lambda: _user()
        try:
            with patch(
                "app.modules.monthly_inputs.application.queries."
                "monthly_inputs_repository"
            ) as repo:
                repo.list_by_period.return_value = []
                reponse = TestClient(app).get(
                    "/api/monthly-inputs?year=2026&month=5"
                )

            assert reponse.status_code == 200
            repo.list_by_period.assert_called_once_with(2026, 5, SOCIETE_A)
        finally:
            _teardown()

    def test_la_creation_impose_la_societe_de_session_pas_le_corps(self):
        app.dependency_overrides[get_current_user] = lambda: _user()
        try:
            with patch(
                "app.modules.monthly_inputs.application.commands."
                "monthly_inputs_repository"
            ) as repo:
                repo.insert_batch.return_value = [{"id": "nouvelle"}]
                reponse = TestClient(app).post(
                    "/api/monthly-inputs",
                    json=[
                        {
                            "employee_id": SALARIE_ID,
                            "year": 2026,
                            "month": 5,
                            "name": "Prime",
                            "amount": 100.0,
                            # Tentative d'injection d'une autre société :
                            "company_id": SOCIETE_B,
                        }
                    ],
                )

            assert reponse.status_code == 201
            lignes = repo.insert_batch.call_args[0][0]
            assert lignes[0]["company_id"] == SOCIETE_A, (
                "La société doit venir de la session, jamais du corps de requête"
            )

            # Seconde barrière : le schéma ignore un company_id du corps.
            from app.modules.monthly_inputs.schemas.requests import MonthlyInput

            modele = MonthlyInput(
                employee_id=SALARIE_ID,
                year=2026,
                month=5,
                name="Prime",
                amount=1.0,
                company_id=SOCIETE_B,
            )
            assert "company_id" not in modele.model_dump()
        finally:
            _teardown()

    def test_la_suppression_est_bornee_a_la_societe_active(self):
        app.dependency_overrides[get_current_user] = lambda: _user()
        try:
            with patch(
                "app.modules.monthly_inputs.application.commands."
                "monthly_inputs_repository"
            ) as repo:
                reponse = TestClient(app).delete("/api/monthly-inputs/saisie-1")

            assert reponse.status_code == 200
            repo.delete_by_id.assert_called_once_with("saisie-1", SOCIETE_A)
        finally:
            _teardown()

    def test_un_collaborateur_ne_liste_pas_les_saisies_de_la_societe(self):
        """La liste du mois est un écran RH : un simple salarié est refusé."""
        app.dependency_overrides[get_current_user] = lambda: _user(
            role="collaborateur"
        )
        try:
            reponse = TestClient(app).get("/api/monthly-inputs?year=2026&month=5")
            assert reponse.status_code == 403
        finally:
            _teardown()
