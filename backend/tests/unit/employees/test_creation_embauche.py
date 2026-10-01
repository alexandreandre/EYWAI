"""Créer un salarié simplement : dans la bonne société, fiche à compléter, planning posé.

Septembre 2026, deux embauches chez Colorplast. La création exigeait numéro de
sécurité sociale et e-mail (souvent inconnus le jour de l'embauche), ne posait
pas le planning (la génération du bulletin s'arrêtait sur « calendrier
incomplet ») et prenait la société principale du profil, pas la société active.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application import commands
from app.modules.employees.infrastructure.mappers import prepare_employee_insert_data

pytestmark = pytest.mark.unit


def _embauche(**modifs):
    donnees = {
        "first_name": "Jeanne",
        "last_name": "Essai",
        "email": None,
        "job_title": "Préparatrice peinture",
        "nir": None,
        "date_naissance": None,
        "lieu_naissance": None,
        "nationalite": None,
        "adresse": None,
        "coordonnees_bancaires": None,
        "hire_date": date(2026, 9, 14),
        "contract_type": "CDI",
        "statut": "Non-Cadre",
        "is_temps_partiel": False,
        "duree_hebdomadaire": 39.0,
        "salaire_de_base": {"valeur": 1990.0},
        "classification_conventionnelle": {"groupe_emploi": "C", "classe_emploi": 710, "coefficient": 710},
        "specificites_paie": {},
        "has_periode_essai": False,
    }
    donnees.update(modifs)
    return donnees


COMPLET = dict(
    email="jeanne.essai@example.com",
    nir="290057300800001",
    date_naissance=date(1990, 5, 15),
    adresse={"rue": "1 rue de l'Essai", "code_postal": "01300", "ville": "Belley"},
    coordonnees_bancaires={"iban": "FR7630006000011234567890189", "bic": "AGRIFRPP"},
)


@pytest.fixture
def infra():
    auth = MagicMock()
    auth.create_user.return_value = "user-1"
    repo = MagicMock()
    repo.create.side_effect = lambda data: {**data}
    with (
        patch.object(commands, "get_auth_provider", return_value=auth),
        patch.object(commands, "get_storage_provider", return_value=MagicMock()),
        patch.object(commands, "get_company_reader", return_value=MagicMock()),
        patch.object(commands, "_profile_repository", MagicMock()),
        patch.object(commands, "_employee_repository", repo),
        patch.object(commands, "_grant_collaborator_company_access"),
        patch.object(commands, "allocate_collaborator_username", return_value="jeanne.essai"),
        patch.object(commands, "generate_credentials_pdf", return_value=b"pdf"),
        patch.object(commands, "on_rib_submitted", return_value=[]),
        patch.object(commands, "_create_trial_period_for_new_employee"),
        patch(
            "app.modules.schedules.application.calendar_generation.appliquer_les_plans_a_un_salarie",
            return_value={"mois": ["2026-09", "2026-10"], "plans": ["Colorplast — 2026"]},
        ) as plans,
    ):
        yield {"auth": auth, "repo": repo, "plans": plans}


async def _creer(donnees):
    return await commands.create_employee(employee_data=donnees, company_id="co-1", granted_by_user_id="rh-1")


@pytest.mark.asyncio
async def test_sans_email_ni_numero_la_fiche_se_cree_en_onboarding(infra):
    resultat = await _creer(_embauche())

    email_technique = infra["auth"].create_user.call_args.kwargs["email"]
    assert email_technique.startswith("import.")
    inseree = infra["repo"].create.call_args.args[0]
    assert "email" not in inseree
    assert inseree["employment_status"] == "en_onboarding"
    assert resultat["acces_application"] is False
    assert resultat["a_completer"] == [
        "Numéro de sécurité sociale",
        "Date de naissance",
        "Adresse postale",
        "Coordonnées bancaires (RIB)",
    ]


@pytest.mark.asyncio
async def test_une_fiche_complete_est_active_d_emblee(infra):
    resultat = await _creer(_embauche(**COMPLET))
    assert infra["repo"].create.call_args.args[0]["employment_status"] == "actif"
    assert resultat["a_completer"] == []
    assert resultat["acces_application"] is True
    assert infra["auth"].create_user.call_args.kwargs["email"] == "jeanne.essai@example.com"


@pytest.mark.asyncio
async def test_le_planning_est_pose_depuis_l_embauche(infra):
    resultat = await _creer(_embauche())
    args = infra["plans"].call_args.args
    assert args[0] == "co-1" and args[2] == date(2026, 9, 14)
    assert resultat["planning_mois"] == ["2026-09", "2026-10"]
    assert resultat["planning_plans"] == ["Colorplast — 2026"]


@pytest.mark.asyncio
async def test_un_planning_en_echec_ne_bloque_pas_l_embauche(infra):
    infra["plans"].side_effect = RuntimeError("base indisponible")
    resultat = await _creer(_embauche())
    assert resultat["planning_mois"] == []
    infra["repo"].create.assert_called_once()


def test_la_preparation_garde_les_champs_absents_vides():
    data = prepare_employee_insert_data(
        _embauche(), new_user_id="u", company_id="c", username="x", folder_name="f"
    )
    assert data["nir"] is None and data["hire_date"] == "2026-09-14"


# --- La route : société active, RH seulement ---

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import get_current_user  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.users.schemas.responses import CompanyAccess, User  # noqa: E402

PRINCIPALE = "11111111-1111-1111-1111-111111111111"
ACTIVE = "22222222-2222-2222-2222-222222222222"


def _utilisateur(role="rh"):
    return User(
        id="33333333-3333-3333-3333-333333333333",
        email="rh@example.com",
        first_name="Rita",
        last_name="Aitch",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=PRINCIPALE, company_name="Principale", role="rh", is_primary=True),
            CompanyAccess(company_id=ACTIVE, company_name="Active", role=role, is_primary=False),
        ],
        active_company_id=ACTIVE,
    )


def _poster(role="rh"):
    import json

    app.dependency_overrides[get_current_user] = lambda: _utilisateur(role)
    try:
        with patch("app.modules.employees.api.router.commands.create_employee") as creer:
            creer.return_value = {
                "id": "e1", "employee_folder_name": "ESSAI_Jeanne", "username": "jeanne.essai",
                "first_name": "Jeanne", "last_name": "Essai", "generated_password": "x" * 12,
                "company_id": ACTIVE, "a_completer": ["Numéro de sécurité sociale"],
                "planning_mois": ["2026-09"], "planning_plans": ["Plan"], "acces_application": False,
            }
            donnees = _embauche()
            donnees["hire_date"] = "2026-09-14"
            reponse = TestClient(app).post(
                "/api/employees", data={"data": json.dumps({**donnees, "nir": "", "email": ""})}
            )
        return reponse, creer
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_le_salarie_est_cree_dans_la_societe_active():
    reponse, creer = _poster()
    assert reponse.status_code == 201, reponse.text
    assert creer.call_args.kwargs["company_id"] == ACTIVE
    assert creer.call_args.kwargs["employee_data"]["nir"] is None
    assert reponse.json()["a_completer"] == ["Numéro de sécurité sociale"]


def test_une_creation_sans_rib_reste_acceptee():
    reponse, creer = _poster()
    assert reponse.status_code == 201
    assert creer.call_args.kwargs["employee_data"].get("coordonnees_bancaires") in (None, {})


def test_un_collaborateur_ne_cree_pas_de_salarie():
    reponse, creer = _poster(role="collaborateur")
    assert reponse.status_code == 403
    creer.assert_not_called()


# --- Le planning du nouveau salarié ---


def test_les_plans_qui_le_couvrent_sont_generes_pour_lui_seul_depuis_l_embauche():
    from app.modules.schedules.application import calendar_generation as cg

    plans = [
        {"id": "p-societe", "name": "Colorplast — 2026", "company_id": "co-1", "scope_type": "company",
         "scope_ref": {}, "template_cycle": ["t1"], "start_date": "2026-01-01", "end_date": "2026-12-31",
         "overwrite_mode": "preserve_manual"},
        {"id": "p-equipe", "name": "Équipe de nuit", "company_id": "co-1", "scope_type": "team",
         "scope_ref": {"team_id": "nuit"}, "template_cycle": ["t2"], "start_date": "2026-01-01",
         "end_date": "2026-12-31"},
        {"id": "p-passe", "name": "Été", "company_id": "co-1", "scope_type": "company",
         "scope_ref": {}, "template_cycle": ["t3"], "start_date": "2026-07-01", "end_date": "2026-08-31"},
    ]
    specs = []

    def generer(spec, **_):
        specs.append(spec)
        return {"employees": [{"months": [{"year": 2026, "month": 9}, {"year": 2026, "month": 10}]}]}

    with (
        patch.object(cg.plans_repo, "resolve_scope_employees", return_value=[{"id": "e1", "team_id": "jour"}]),
        patch.object(cg.plans_repo, "list_plans", return_value=plans),
        patch.object(cg, "generate", side_effect=generer),
    ):
        resultat = cg.appliquer_les_plans_a_un_salarie("co-1", "e1", date(2026, 9, 14))

    assert [s.plan_id for s in specs] == ["p-societe"]
    assert specs[0].employee_ids == ["e1"]
    assert specs[0].start_date == date(2026, 9, 14)
    assert specs[0].overwrite_mode == "preserve_manual"
    assert resultat == {"mois": ["2026-09", "2026-10"], "plans": ["Colorplast — 2026"]}


def test_sans_plan_rien_n_est_pose():
    from app.modules.schedules.application import calendar_generation as cg

    with (
        patch.object(cg.plans_repo, "resolve_scope_employees", return_value=[{"id": "e1"}]),
        patch.object(cg.plans_repo, "list_plans", return_value=[]),
        patch.object(cg, "generate") as generer,
    ):
        assert cg.appliquer_les_plans_a_un_salarie("co-1", "e1", date(2026, 9, 14)) == {"mois": [], "plans": []}
    generer.assert_not_called()


# --- Les valeurs proposées ---


def test_les_valeurs_d_embauche_sont_reservees_a_la_rh_de_la_societe_active():
    app.dependency_overrides[get_current_user] = lambda: _utilisateur("collaborateur")
    try:
        with patch("app.modules.employees.api.router.queries.get_valeurs_embauche") as lire:
            refuse = TestClient(app).get("/api/employees/valeurs-embauche")
        app.dependency_overrides[get_current_user] = lambda: _utilisateur("rh")
        with patch(
            "app.modules.employees.api.router.queries.get_valeurs_embauche",
            return_value={"statut": "Non-Cadre"},
        ) as lire_rh:
            ok = TestClient(app).get("/api/employees/valeurs-embauche")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert refuse.status_code == 403
    lire.assert_not_called()
    assert ok.status_code == 200 and ok.json() == {"statut": "Non-Cadre"}
    assert lire_rh.call_args.args == (ACTIVE,)
