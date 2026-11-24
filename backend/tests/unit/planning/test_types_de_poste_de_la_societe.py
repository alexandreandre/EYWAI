"""Types de poste : ceux de la société, plus ceux (partagés) de sa convention planning.

Constat du guide 1 (17/11) : sans convention planning, l'écran listait les types
actifs de toutes les conventions (postes en double) et laissait les modifier.

Constat du 24/11 (lot C, « L'action n'a pas abouti ») : un type de poste
n'appartenait qu'à une convention, partagée par plusieurs sociétés du groupe.
Désormais un type créé ou modifié depuis une société lui appartient
(`shift_types.company_id`) ; un type de convention n'est jamais réécrit :
le modifier crée une copie propre à la société, qui le remplace pour elle seule.
"""

from __future__ import annotations

import pytest

from app.modules.planning.application import commands, queries, shift_type_commands
from app.modules.planning.infrastructure.repository import planning_repository
from app.modules.planning.schemas.requests import CompanyPlanningSettingsUpdate

pytestmark = pytest.mark.unit

TYPE_CONVENTION = {
    "id": "t-cc",
    "code": "MATIN",
    "label": "Matin",
    "color": "#22c55e",
    "default_start": "05:00:00",
    "default_end": "13:00:00",
    "paid_break_minutes": 20,
    "unpaid_break_minutes": 30,
    "night_windows": [],
    "meal_allowance_eligible": True,
    "allows_overnight": False,
    "is_active": True,
    "is_custom": False,
    "premium_rule_code": None,
    "created_at": "2026-04-22T00:00:00+00:00",
    "collective_agreement_id": "cc-1",
    "company_id": None,
}


@pytest.fixture
def repo(monkeypatch):
    etat = {
        "cc": None,
        "partages": [dict(TYPE_CONVENTION)],
        "propres": [],
        "par_id": {},
        "crees": [],
        "maj": [],
        "desactives": [],
    }

    def par_id(sid):
        if sid in etat["par_id"]:
            return etat["par_id"][sid]
        for t in etat["partages"] + etat["propres"]:
            if t["id"] == sid:
                return t
        return None

    def creer(data):
        # Ni l'id ni la date du type partagé ne sont recopiés.
        assert "id" not in data and "created_at" not in data
        ligne = {**data, "id": f"neuf-{len(etat['crees']) + 1}"}
        etat["crees"].append(ligne)
        return ligne

    monkeypatch.setattr(
        planning_repository,
        "get_company_planning_settings",
        lambda cid: {"collective_agreement_id": etat["cc"]},
    )
    monkeypatch.setattr(
        planning_repository,
        "get_shift_types_by_cc",
        lambda cc: [t for t in etat["partages"] if t["collective_agreement_id"] == cc],
    )
    monkeypatch.setattr(
        planning_repository,
        "get_shift_types_by_company",
        lambda cid: [t for t in etat["propres"] if t["company_id"] == cid],
    )
    monkeypatch.setattr(
        planning_repository,
        "get_all_active_shift_types",
        lambda: pytest.fail("types de toutes les conventions lus"),
    )
    monkeypatch.setattr(planning_repository, "get_shift_type_by_id", par_id)
    monkeypatch.setattr(planning_repository, "create_shift_type", creer)
    monkeypatch.setattr(
        planning_repository,
        "update_shift_type",
        lambda sid, d: etat["maj"].append((sid, d)) or {**par_id(sid), **d},
    )
    monkeypatch.setattr(
        planning_repository,
        "deactivate_shift_type",
        lambda sid: etat["desactives"].append(sid),
    )
    return etat


def _propre(**kw):
    base = {
        **TYPE_CONVENTION,
        "id": "t-co",
        "collective_agreement_id": None,
        "company_id": "co-1",
        "is_custom": True,
        "replaces_shift_type_id": None,
    }
    return {**base, **kw}


# --- Lecture ---------------------------------------------------------------


def test_sans_convention_ni_type_propre_aucun_type(repo):
    assert queries.get_shift_types_for_company("co-1") == []


def test_sans_convention_les_types_de_la_societe(repo):
    repo["propres"] = [_propre(code="SOIR", id="t-soir")]
    types = queries.get_shift_types_for_company("co-1")
    assert [(t["code"], t["origine"]) for t in types] == [("SOIR", "societe")]


def test_avec_convention_ses_types_partages(repo):
    repo["cc"] = "cc-1"
    types = queries.get_shift_types_for_company("co-1")
    assert [(t["code"], t["origine"]) for t in types] == [("MATIN", "convention")]


def test_le_type_de_la_societe_passe_avant_celui_de_la_convention(repo):
    repo["cc"] = "cc-1"
    repo["propres"] = [
        _propre(id="t-copie", paid_break_minutes=10, replaces_shift_type_id="t-cc"),
        _propre(id="t-nuit", code="NUIT", label="Nuit"),
    ]
    types = queries.get_shift_types_for_company("co-1")
    assert [(t["id"], t["code"]) for t in types] == [("t-copie", "MATIN"), ("t-nuit", "NUIT")]
    assert types[0]["paid_break_minutes"] == 10


def test_meme_code_que_la_convention_la_societe_l_emporte(repo):
    repo["cc"] = "cc-1"
    repo["propres"] = [_propre(id="t-matin-co", code="matin")]
    types = queries.get_shift_types_for_company("co-1")
    assert [t["id"] for t in types] == ["t-matin-co"]


def test_les_types_d_une_autre_societe_ne_se_voient_pas(repo):
    repo["propres"] = [_propre(company_id="co-2")]
    assert queries.get_shift_types_for_company("co-1") == []


# --- Création --------------------------------------------------------------


@pytest.mark.parametrize("cc", [None, "cc-1"])
def test_creer_un_type_appartient_a_la_societe_avec_ou_sans_convention(repo, cc):
    repo["cc"] = cc
    cree = shift_type_commands.create_shift_type("co-1", {"code": "SOIR", "label": "Soir"})
    assert cree["company_id"] == "co-1"
    assert cree["collective_agreement_id"] is None
    assert repo["maj"] == []


def test_creer_sans_couleur_en_donne_une(repo):
    """`shift_types.color` est NOT NULL en base : sans couleur, l'insertion échouait."""
    cree = shift_type_commands.create_shift_type(
        "co-1", {"code": "SOIR", "label": "Soir", "color": None}
    )
    assert cree["color"]


def test_creer_un_code_deja_pris_par_la_societe_dit_pourquoi(repo):
    repo["propres"] = [_propre(code="SOIR")]
    with pytest.raises(ValueError, match="SOIR"):
        shift_type_commands.create_shift_type("co-1", {"code": "soir", "label": "Soir"})
    assert repo["crees"] == []


# --- Modification ----------------------------------------------------------


def test_modifier_un_type_de_la_societe_l_ecrit(repo):
    repo["propres"] = [_propre()]
    shift_type_commands.update_shift_type("co-1", "t-co", {"paid_break_minutes": 15})
    assert repo["maj"] == [("t-co", {"paid_break_minutes": 15})]


def test_modifier_un_type_de_convention_cree_une_copie_de_la_societe(repo):
    repo["cc"] = "cc-1"
    copie = shift_type_commands.update_shift_type(
        "co-1", "t-cc", {"paid_break_minutes": 15}
    )
    # Le type partagé n'est jamais réécrit.
    assert repo["maj"] == []
    assert len(repo["crees"]) == 1
    assert copie["company_id"] == "co-1"
    assert copie["collective_agreement_id"] is None
    assert copie["replaces_shift_type_id"] == "t-cc"
    assert copie["paid_break_minutes"] == 15
    assert copie["code"] == "MATIN" and copie["unpaid_break_minutes"] == 30


def test_modifier_un_type_de_convention_deja_copie_met_a_jour_la_copie(repo):
    repo["cc"] = "cc-1"
    repo["propres"] = [_propre(id="t-copie", replaces_shift_type_id="t-cc")]
    shift_type_commands.update_shift_type("co-1", "t-cc", {"paid_break_minutes": 5})
    assert repo["crees"] == []
    assert repo["maj"] == [("t-copie", {"paid_break_minutes": 5})]


@pytest.mark.parametrize("cc", [None, "cc-2"])
def test_un_type_d_une_autre_convention_ne_se_modifie_pas(repo, cc):
    repo["cc"] = cc
    with pytest.raises(PermissionError):
        shift_type_commands.update_shift_type("co-1", "t-cc", {"paid_break_minutes": 10})
    with pytest.raises(PermissionError):
        shift_type_commands.delete_shift_type("co-1", "t-cc")
    assert repo["maj"] == [] and repo["crees"] == [] and repo["desactives"] == []


def test_un_type_d_une_autre_societe_ne_se_modifie_pas(repo):
    repo["propres"] = [_propre(company_id="co-2")]
    with pytest.raises(PermissionError):
        shift_type_commands.update_shift_type("co-1", "t-co", {"paid_break_minutes": 10})
    with pytest.raises(PermissionError):
        shift_type_commands.delete_shift_type("co-1", "t-co")
    assert repo["maj"] == [] and repo["desactives"] == []


def test_type_introuvable(repo):
    with pytest.raises(LookupError):
        shift_type_commands.update_shift_type("co-1", "absent", {"code": "X"})


# --- Désactivation ---------------------------------------------------------


def test_desactiver_un_type_de_la_societe(repo):
    repo["propres"] = [_propre()]
    shift_type_commands.delete_shift_type("co-1", "t-co")
    assert repo["desactives"] == ["t-co"]


def test_desactiver_un_type_de_convention_le_masque_pour_la_societe_seule(repo):
    repo["cc"] = "cc-1"
    shift_type_commands.delete_shift_type("co-1", "t-cc")
    assert repo["desactives"] == []
    assert len(repo["crees"]) == 1
    copie = repo["crees"][0]
    assert copie["company_id"] == "co-1"
    assert copie["replaces_shift_type_id"] == "t-cc"
    assert copie["is_active"] is False


# --- Convention du planning ------------------------------------------------


def test_convention_inconnue_du_planning_message_clair(monkeypatch):
    """Cause du 24/11 : l'écran proposait les conventions du catalogue, dont les
    identifiants n'existent pas dans le référentiel du planning (clé étrangère
    violée, erreur 500, « L'action n'a pas abouti »)."""
    monkeypatch.setattr(planning_repository, "get_cc_by_id", lambda cc: None)
    monkeypatch.setattr(
        planning_repository,
        "update_company_planning_settings",
        lambda cid, d: pytest.fail("écriture d'une convention inconnue"),
    )
    with pytest.raises(ValueError, match="convention"):
        commands.update_company_settings(
            CompanyPlanningSettingsUpdate(
                collective_agreement_id="39e86454-778b-4913-ac4a-2b01735f89ef"
            ),
            "co-1",
        )


def test_convention_du_referentiel_enregistree(monkeypatch):
    ecrit = []
    monkeypatch.setattr(planning_repository, "get_cc_by_id", lambda cc: {"id": cc})
    monkeypatch.setattr(
        planning_repository,
        "update_company_planning_settings",
        lambda cid, d: ecrit.append(d) or {"company_id": cid, **d},
    )
    cc = "0dec56b2-ea4d-4fa8-9a9b-6daad0345039"
    commands.update_company_settings(
        CompanyPlanningSettingsUpdate(collective_agreement_id=cc), "co-1"
    )
    assert ecrit == [{"collective_agreement_id": cc}]


def test_retirer_la_convention_sans_verification(monkeypatch):
    ecrit = []
    monkeypatch.setattr(
        planning_repository, "get_cc_by_id", lambda cc: pytest.fail("pas de lecture")
    )
    monkeypatch.setattr(
        planning_repository,
        "update_company_planning_settings",
        lambda cid, d: ecrit.append(d) or {},
    )
    commands.update_company_settings(
        CompanyPlanningSettingsUpdate(collective_agreement_id=None), "co-1"
    )
    assert ecrit == [{"collective_agreement_id": None}]


def test_conventions_du_planning_listees(monkeypatch):
    monkeypatch.setattr(
        planning_repository,
        "get_all_collective_agreements",
        lambda: [{"id": "cc-1", "code": "GENERIC_STD", "label": "Générique", "idcc": None}],
    )
    assert queries.list_planning_collective_agreements() == [
        {"id": "cc-1", "code": "GENERIC_STD", "label": "Générique", "idcc": None}
    ]


# --- Relecture du 24/11 ----------------------------------------------------


def test_les_types_desactives_ne_sont_pas_proposes(repo):
    repo["cc"] = "cc-1"
    repo["partages"].append({**TYPE_CONVENTION, "id": "t-vieux", "code": "SOIR", "is_active": False})
    repo["propres"] = [_propre(id="t-off", code="NUIT", is_active=False)]
    assert [t["code"] for t in queries.get_shift_types_for_company("co-1")] == ["MATIN"]


def test_un_type_desactive_de_la_societe_ne_masque_pas_par_son_code(repo):
    """Une ancienne copie désactivée ne cache que le poste qu'elle remplace."""
    repo["cc"] = "cc-1"
    repo["propres"] = [_propre(id="t-off", is_active=False, replaces_shift_type_id="t-autre-cc")]
    assert [t["id"] for t in queries.get_shift_types_for_company("co-1")] == ["t-cc"]


def test_la_copie_desactivee_masque_le_poste_remplace(repo):
    repo["cc"] = "cc-1"
    repo["propres"] = [_propre(id="t-off", is_active=False, replaces_shift_type_id="t-cc")]
    assert queries.get_shift_types_for_company("co-1") == []


def test_recreer_un_code_desactive_le_reactive(repo):
    repo["propres"] = [_propre(code="SOIR", is_active=False)]
    shift_type_commands.create_shift_type("co-1", {"code": "soir", "label": "Soir 2"})
    assert repo["crees"] == []
    assert repo["maj"] == [("t-co", {"code": "soir", "label": "Soir 2", "is_active": True})]


def test_la_copie_d_un_poste_de_convention_est_active(repo):
    repo["cc"] = "cc-1"
    copie = shift_type_commands.update_shift_type("co-1", "t-cc", {"label": "Matin long"})
    assert copie["is_active"] is True


def test_deux_modifications_simultanees_une_seule_copie(repo, monkeypatch):
    """La seconde requête bute sur l'unicité (23505) : elle relit la copie et l'écrit."""
    repo["cc"] = "cc-1"
    copie_concurrente = _propre(id="t-copie", replaces_shift_type_id="t-cc")

    class Doublon(Exception):
        code = "23505"

    def creer_en_conflit(data):
        repo["propres"].append(copie_concurrente)
        raise Doublon("duplicate key value violates unique constraint")

    monkeypatch.setattr(planning_repository, "create_shift_type", creer_en_conflit)
    shift_type_commands.update_shift_type("co-1", "t-cc", {"meal_allowance_eligible": False})
    assert repo["maj"] == [("t-copie", {"meal_allowance_eligible": False})]


def test_supprimer_un_poste_de_convention_deja_masque_ne_dit_pas_code_pris(repo):
    repo["cc"] = "cc-1"
    repo["propres"] = [_propre(id="t-matin-co")]
    shift_type_commands.delete_shift_type("co-1", "t-cc")
    assert repo["crees"] == [] and repo["desactives"] == []


@pytest.mark.parametrize("cc", ["", "pas-un-uuid"])
def test_convention_vide_ou_mal_formee(monkeypatch, cc):
    ecrit = []
    monkeypatch.setattr(
        planning_repository, "get_cc_by_id", lambda c: pytest.fail("lecture d'un id invalide")
    )
    monkeypatch.setattr(
        planning_repository,
        "update_company_planning_settings",
        lambda cid, d: ecrit.append(d) or {},
    )
    if cc == "":
        commands.update_company_settings(
            CompanyPlanningSettingsUpdate(collective_agreement_id=cc), "co-1"
        )
        assert ecrit == [{"collective_agreement_id": None}]
    else:
        with pytest.raises(ValueError, match="convention"):
            commands.update_company_settings(
                CompanyPlanningSettingsUpdate(collective_agreement_id=cc), "co-1"
            )


def test_creer_en_doublon_concurrent_message_clair(repo, monkeypatch):
    class Doublon(Exception):
        code = "23505"

    def creer(data):
        raise Doublon("duplicate key")

    monkeypatch.setattr(planning_repository, "create_shift_type", creer)
    with pytest.raises(ValueError, match="SOIR"):
        shift_type_commands.create_shift_type("co-1", {"code": "SOIR", "label": "Soir"})
