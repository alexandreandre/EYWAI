"""Règle des heures sup par salarié (retour d'Elsa, Cartol, 20/11/2026).

Les alternants d'une société à compteur ne suivent pas la règle de la société :
leurs heures sup sont « toujours payées ». Le réglage du salarié (null = règle
de la société) prend la place de la politique de la société partout où elle est
lue pour lui. Sans réglage, rien ne change : c'est le point qui compte.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.modules.modulation.application import payroll_hook as hook
from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.modulation.infrastructure import repository as repo

pytestmark = [pytest.mark.unit, pytest.mark.regle_heures_sup_en_base]


def _calendrier(*heures: float) -> list[dict]:
    return [{"type": "travail_hs25", "heures": h} for h in heures]


@pytest.fixture
def compteur(monkeypatch):
    """Société à compteur, salarié sans mouvement, aucune décision du mois."""
    etat = {
        "settings": ModulationSettings(
            hour_account_enabled=True, hs_routing_policy="franchise",
            hs_franchise_hours_per_period=14,
        ),
        "regle_salarie": None,
        "decision": None,
        "mouvements": [],
    }
    insertion = Mock(return_value={"id": "mov-1"})
    lecture_regle = Mock(side_effect=lambda _eid: etat["regle_salarie"])
    monkeypatch.setattr(hook.repo, "get_modulation_settings", lambda _cid: etat["settings"])
    monkeypatch.setattr(hook.repo, "get_hs_routing_override", lecture_regle)
    monkeypatch.setattr(hook.repo, "list_movements_for_employee", lambda _eid: etat["mouvements"])
    monkeypatch.setattr(hook.repo, "insert_movement", insertion)
    monkeypatch.setattr(hook, "_decision_du_mois", lambda *_a: etat["decision"])
    monkeypatch.setattr(hook, "sync_account_balance_cache", Mock())
    monkeypatch.setattr(hook, "sync_employee_modulation_counter", Mock())
    etat["insertion"] = insertion
    etat["lecture_regle"] = lecture_regle
    return etat


def _router(etat, *heures: float):
    return hook.apply_modulation_hour_account_to_calendar(
        "soc-1", "emp-1", 2026, 10, _calendrier(*heures),
        majorations={"travail_hs25": 0.25},
    )


def _hs_payees(calendrier: list[dict]) -> float:
    return round(sum(float(j["heures"]) for j in calendrier if j["type"] == "travail_hs25"), 2)


# --- Sans réglage : strictement comme avant ---


@pytest.mark.parametrize(
    ("politique", "attendu"),
    [
        # (heures sup payées, heures au compteur, repos crédité)
        ("pay_all", (20.0, 0.0, 0.0)),
        ("account_all", (0.0, 20.0, 25.0)),
        ("franchise", (6.0, 14.0, 17.5)),
        ("manual", (20.0, 0.0, 0.0)),
    ],
)
def test_sans_reglage_le_salarie_suit_la_societe(compteur, politique, attendu):
    compteur["settings"] = ModulationSettings(
        hour_account_enabled=True, hs_routing_policy=politique,
        hs_franchise_hours_per_period=14,
    )
    calendrier, _ids, resultat = _router(compteur, 12, 8)
    assert (_hs_payees(calendrier), resultat.hs_credited, resultat.repos_credite) == attendu
    assert resultat.regle == politique


def test_sans_compteur_la_regle_du_salarie_n_est_meme_pas_lue(compteur):
    """Société sans compteur : rien ne change, et aucune lecture de plus."""
    compteur["settings"] = ModulationSettings(hour_account_enabled=False)
    compteur["regle_salarie"] = "account_all"
    calendrier, ids, resultat = _router(compteur, 10)
    assert _hs_payees(calendrier) == 10.0
    assert ids == [] and resultat.hs_credited == 0.0
    compteur["lecture_regle"].assert_not_called()


# --- « Toujours payées » ---


@pytest.mark.parametrize("politique", ["account_all", "franchise", "manual"])
def test_toujours_payees_rien_ne_va_au_compteur(compteur, politique):
    compteur["settings"] = ModulationSettings(
        hour_account_enabled=True, hs_routing_policy=politique,
        hs_franchise_hours_per_period=14,
    )
    compteur["regle_salarie"] = "pay_all"
    calendrier, ids, resultat = _router(compteur, 12, 8)
    assert _hs_payees(calendrier) == 20.0
    assert (resultat.hs_credited, resultat.repos_credite, resultat.hs_paid) == (0.0, 0.0, 20.0)
    assert ids == []
    compteur["insertion"].assert_not_called()
    # L'écran du bulletin propose alors « Mettre ces heures au compteur ».
    assert resultat.regle == "pay_all"


# --- « Toujours au compteur » ---


def test_toujours_au_compteur_dans_une_societe_qui_paie(compteur):
    compteur["settings"] = ModulationSettings(hour_account_enabled=True, hs_routing_policy="pay_all")
    compteur["regle_salarie"] = "account_all"
    calendrier, ids, resultat = _router(compteur, 4)
    assert _hs_payees(calendrier) == 0.0
    assert (resultat.hs_credited, resultat.repos_credite) == (4.0, 5.0)
    assert ids == ["mov-1"]
    assert compteur["insertion"].call_args[0][0]["hours"] == 5.0
    assert resultat.regle == "account_all"


def test_le_choix_du_mois_l_emporte_sur_la_regle_du_salarie(compteur):
    """« Payer ces heures ce mois-ci » reste possible pour un salarié au compteur."""
    compteur["settings"] = ModulationSettings(hour_account_enabled=True, hs_routing_policy="pay_all")
    compteur["regle_salarie"] = "account_all"
    compteur["decision"] = {"hours_to_account": 0, "status": "validated"}
    calendrier, ids, resultat = _router(compteur, 4)
    assert _hs_payees(calendrier) == 4.0
    assert ids == [] and resultat.paye_ce_mois


# --- Le pied du bulletin (compteur « Récup. ») ---


def test_le_pied_du_bulletin_suit_la_regle_du_salarie(compteur):
    compteur["settings"] = ModulationSettings(hour_account_enabled=True, hs_routing_policy="account_all")
    assert hook.etat_recuperation_du_bulletin("soc-1", "emp-1", 2026, 10) is not None
    compteur["regle_salarie"] = "pay_all"
    # Toujours payées, aucun compteur : rien à imprimer, comme une société qui paie.
    assert hook.etat_recuperation_du_bulletin("soc-1", "emp-1", 2026, 10) is None

    compteur["settings"] = ModulationSettings(hour_account_enabled=True, hs_routing_policy="pay_all")
    compteur["regle_salarie"] = None
    assert hook.etat_recuperation_du_bulletin("soc-1", "emp-1", 2026, 10) is None
    compteur["regle_salarie"] = "account_all"
    assert hook.etat_recuperation_du_bulletin("soc-1", "emp-1", 2026, 10) is not None


# --- Lecture du réglage ---


def test_colonne_absente_la_paie_garde_la_regle_de_la_societe(monkeypatch, caplog):
    """Code déployé avant la migration : la paie ne tombe pas, elle suit la règle
    de la société (comme avant), et le journal le dit ; la pose est refusée."""
    from postgrest.exceptions import APIError

    absente = APIError({"message": "column does not exist", "code": "42703", "hint": None, "details": None})
    monkeypatch.setattr(repo.supabase, "table", Mock(side_effect=absente))
    with caplog.at_level("WARNING"):
        assert repo.get_hs_routing_override("emp-1") is None
        assert repo.list_hs_routing_overrides("soc-1") == {}
    assert "colonne absente" in caplog.text
    with pytest.raises(repo.RegleHeuresSupIndisponible):
        repo.set_hs_routing_override("soc-1", "emp-1", "pay_all")


def test_une_autre_panne_remonte(monkeypatch):
    """Base indisponible : le bulletin ne se calcule pas sur une règle devinée."""
    monkeypatch.setattr(repo.supabase, "table", Mock(side_effect=RuntimeError("base indisponible")))
    with pytest.raises(RuntimeError):
        repo.get_hs_routing_override("emp-1")
    with pytest.raises(RuntimeError):
        repo.list_hs_routing_overrides("soc-1")


@pytest.mark.parametrize("valeur", [None, "pay_all", "account_all", "franchise", "n'importe quoi"])
def test_seules_deux_regles_sont_lues(monkeypatch, valeur):
    from tests.unit.base_en_memoire import BaseEnMemoire

    base = BaseEnMemoire({"employees": [{"id": "emp-1", "company_id": "soc-1", "hs_routing_override": valeur}]})
    base.brancher(monkeypatch)
    attendu = valeur if valeur in ("pay_all", "account_all") else None
    assert repo.get_hs_routing_override("emp-1") == attendu
    assert repo.list_hs_routing_overrides("soc-1") == ({"emp-1": attendu} if attendu else {})


def test_poser_et_retirer_le_reglage(monkeypatch):
    from tests.unit.base_en_memoire import BaseEnMemoire

    base = BaseEnMemoire({"employees": [{"id": "emp-1", "company_id": "soc-1", "hs_routing_override": None}]})
    base.brancher(monkeypatch)
    assert repo.set_hs_routing_override("soc-1", "emp-1", "pay_all") is True
    assert base.ligne("employees", id="emp-1")["hs_routing_override"] == "pay_all"
    assert repo.set_hs_routing_override("soc-1", "emp-1", None) is True
    assert base.ligne("employees", id="emp-1")["hs_routing_override"] is None
    # Salarié d'une autre société : rien n'est écrit.
    assert repo.set_hs_routing_override("soc-2", "emp-1", "pay_all") is False
    assert base.ligne("employees", id="emp-1")["hs_routing_override"] is None


# --- Routage manuel et départ ---


def test_routage_manuel_le_salarie_a_regle_propre_n_attend_pas_de_decision(monkeypatch):
    from app.modules.modulation.application import overtime_routing_queries as otr
    from tests.unit.base_en_memoire import BaseEnMemoire

    base = BaseEnMemoire(
        {
            "employees": [
                {"id": "emp-1", "company_id": "soc-1", "employment_status": "actif",
                 "first_name": "A", "last_name": "B", "duree_hebdomadaire": 35,
                 "hs_routing_override": "pay_all"},
                {"id": "emp-2", "company_id": "soc-1", "employment_status": "actif",
                 "first_name": "C", "last_name": "D", "duree_hebdomadaire": 35,
                 "hs_routing_override": None},
            ],
        }
    )
    base.brancher(monkeypatch)
    monkeypatch.setattr(
        otr.mod_repo, "get_modulation_settings",
        lambda _cid: ModulationSettings(hour_account_enabled=True, hs_routing_policy="manual"),
    )
    monkeypatch.setattr(otr.otr_repo, "list_for_period", lambda *_a: [])
    monkeypatch.setattr(otr, "_employee_hs_for_month", lambda *_a: 5.0)
    lignes = otr.list_overtime_routing("soc-1", 2026, 10)
    assert [l["employee_id"] for l in lignes] == ["emp-2"]


def test_alerte_de_depart_suit_la_regle_du_salarie(monkeypatch):
    from app.modules.payroll.engine import alertes_de_sortie as sortie

    monkeypatch.setattr(
        sortie, "_reglages_modulation",
        lambda _cid: {"hour_account_enabled": True, "hs_routing_policy": "account_all"},
    )
    monkeypatch.setattr(sortie, "_mouvements_du_compteur", lambda _eid: [])
    with patch.object(repo, "get_hs_routing_override", return_value=None):
        assert sortie.alerte_modulation_au_depart("emp-1", "soc-1") == []
    with patch.object(repo, "get_hs_routing_override", return_value="pay_all"):
        assert len(sortie.alerte_modulation_au_depart("emp-1", "soc-1")) == 1


# --- Routes de la fiche et compte de l'écran du compteur ---

_SOCIETE = "aaaaaaaa-1111-1111-1111-111111111111"
_SALARIE = "bbbbbbbb-2222-2222-2222-222222222222"
_AILLEURS = "cccccccc-3333-3333-3333-333333333333"


def _client(role: str):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.security import get_current_user
    from app.modules.modulation.api.router import router
    from app.modules.users.schemas.responses import CompanyAccess, User

    compte = User(
        id="dddddddd-4444-4444-4444-444444444444",
        email="compte@societe-a.fr",
        first_name="R",
        last_name="H",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(company_id=_SOCIETE, company_name="Société A", role=role, is_primary=True)
        ],
        active_company_id=_SOCIETE,
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: compte
    return TestClient(app)


@pytest.fixture
def base_salarie(monkeypatch):
    from fastapi import HTTPException

    from app.modules.modulation.api import router as routes
    from tests.unit.base_en_memoire import BaseEnMemoire

    base = BaseEnMemoire(
        {
            "employees": [
                {"id": _SALARIE, "company_id": _SOCIETE, "hs_routing_override": None,
                 "employment_status": "actif"},
                {"id": "autre", "company_id": _SOCIETE, "hs_routing_override": "pay_all",
                 "employment_status": "actif"},
                # Parti : ne compte plus sur l'écran de la société.
                {"id": "parti", "company_id": _SOCIETE, "hs_routing_override": "account_all",
                 "employment_status": "parti"},
                {"id": _AILLEURS, "company_id": "autre-societe", "hs_routing_override": None,
                 "employment_status": "actif"},
            ],
            "company_modulation_settings": [
                {"company_id": _SOCIETE, "hour_account_enabled": True, "hs_routing_policy": "account_all"}
            ],
        }
    )
    base.brancher(monkeypatch)
    # Sur la classe : un attribut posé sur l'instance y resterait après le test
    # (monkeypatch y remet la méthode liée) et masquerait les doublures des suivants.
    def perimetre(_self, societe, salarie):
        if base.lignes("employees", id=salarie, company_id=societe) == []:
            raise HTTPException(status_code=404, detail="Ressource introuvable")

    monkeypatch.setattr(type(routes.access_control_service), "assert_employee_in_company", perimetre)
    return base


def test_la_fiche_lit_et_pose_la_regle_du_salarie(base_salarie):
    client = _client("rh")
    url = f"/api/modulation/employees/{_SALARIE}/regle-heures-sup"
    assert client.get(url).json() == {
        "regle": None, "regle_societe": "account_all", "compteur_ouvert": True,
    }
    r = client.put(url, json={"regle": "pay_all"})
    assert r.status_code == 200 and r.json()["regle"] == "pay_all"
    assert base_salarie.ligne("employees", id=_SALARIE)["hs_routing_override"] == "pay_all"
    reglages = client.get("/api/modulation/settings").json()
    assert (reglages["salaries_regle_propre"], reglages["salaries_toujours_au_compteur"]) == (2, 0)
    r = client.put(url, json={"regle": None})
    assert r.json()["regle"] is None
    assert base_salarie.ligne("employees", id=_SALARIE)["hs_routing_override"] is None
    assert client.put(url, json={"regle": "franchise"}).status_code == 422


def test_seule_la_rh_pose_la_regle(base_salarie):
    url = f"/api/modulation/employees/{_SALARIE}/regle-heures-sup"
    assert _client("collaborateur").put(url, json={"regle": "pay_all"}).status_code == 403
    assert base_salarie.ligne("employees", id=_SALARIE)["hs_routing_override"] is None


def test_le_salarie_d_une_autre_societe_n_est_pas_touche(base_salarie):
    url = f"/api/modulation/employees/{_AILLEURS}/regle-heures-sup"
    assert _client("rh").put(url, json={"regle": "pay_all"}).status_code == 404
    assert base_salarie.ligne("employees", id=_AILLEURS)["hs_routing_override"] is None


def test_le_compteur_ne_se_coupe_pas_sous_un_salarie_toujours_au_compteur(base_salarie):
    client = _client("rh")
    base_salarie.ligne("company_modulation_settings", company_id=_SOCIETE)["hs_routing_policy"] = "pay_all"
    client.put(f"/api/modulation/employees/{_SALARIE}/regle-heures-sup", json={"regle": "account_all"})
    assert client.get("/api/modulation/settings").json()["salaries_toujours_au_compteur"] == 1
    r = client.patch("/api/modulation/settings", json={"hour_account_enabled": False})
    assert r.status_code == 400 and "toujours au compteur" in r.json()["detail"]
    assert base_salarie.ligne("company_modulation_settings", company_id=_SOCIETE)["hour_account_enabled"] is True
    # Remis à la règle de la société : le compteur se coupe.
    client.put(f"/api/modulation/employees/{_SALARIE}/regle-heures-sup", json={"regle": None})
    assert client.patch("/api/modulation/settings", json={"hour_account_enabled": False}).status_code == 200


def test_avant_la_migration_la_pose_dit_pourquoi(base_salarie, monkeypatch):
    monkeypatch.setattr(
        repo, "set_hs_routing_override",
        Mock(side_effect=repo.RegleHeuresSupIndisponible()),
    )
    r = _client("rh").put(f"/api/modulation/employees/{_SALARIE}/regle-heures-sup", json={"regle": "pay_all"})
    assert r.status_code == 409 and "pas encore disponible" in r.json()["detail"]
