"""Tests import BOETH depuis DSN."""

from unittest.mock import patch

from app.modules.dsn_import.application.boeth_import import (
    apply_dsn_boeth_on_commit,
    append_boeth_review_conflict,
    extract_boeth_from_contrat,
    normalize_boeth_code,
)
from app.modules.dsn_import.application.commit import commit_batch
from app.modules.dsn_import.application.mapping import map_employee_payload
from app.modules.dsn_import.domain.model import ContratBlock, EtablissementBlock, IndividuBlock
from app.modules.dsn_import.domain.rubriques import R_S21_CTR_STATUT_BOETH


def _ind_with_boeth(code: str) -> IndividuBlock:
    contrat = ContratBlock(
        date_debut="20200115",
        rubriques={R_S21_CTR_STATUT_BOETH: code},
    )
    return IndividuBlock(
        nom="MARTIN",
        prenom="Jean",
        nir="180032710123448",
        contrats=[contrat],
    )


def test_normalize_boeth_code():
    assert normalize_boeth_code("1") == "01"
    assert normalize_boeth_code("01") == "01"
    assert normalize_boeth_code("08") == "08"
    assert normalize_boeth_code("99") is None
    assert normalize_boeth_code("") is None


def test_extract_boeth_from_contrat():
    contrat = ContratBlock(rubriques={R_S21_CTR_STATUT_BOETH: "01"})
    boeth = extract_boeth_from_contrat(contrat, valid_from="2020-01-15")
    assert boeth == {
        "boeth_code": "01",
        "valid_from": "2020-01-15",
        "notes": "Import DSN",
    }


def test_map_employee_payload_includes_boeth():
    ind = _ind_with_boeth("01")
    etab = EtablissementBlock()
    payload = map_employee_payload(ind, etab, "44306184100047")
    assert payload["_boeth"]["boeth_code"] == "01"
    assert payload["_boeth"]["valid_from"] == "2020-01-15"


def test_map_employee_payload_no_boeth_when_invalid():
    ind = _ind_with_boeth("99")
    payload = map_employee_payload(ind, EtablissementBlock(), "44306184100047")
    assert "_boeth" not in payload


def test_append_boeth_review_conflict():
    item = {
        "mapped_payload": {"_boeth": {"boeth_code": "01"}},
        "existing_employee_id": "emp-1",
        "review_reasons": [],
        "needs_review": False,
    }
    with patch(
        "app.modules.dsn_import.application.boeth_import.boeth_profiles_repository.get_active_by_employee",
        return_value={"company_id": "co-1", "boeth_code": "08"},
    ):
        append_boeth_review_conflict(item, "co-1")
    assert "boeth_conflict" in item["review_reasons"]
    assert item["needs_review"] is True
    assert item["boeth_conflict"] == {"dsn_code": "01", "profile_code": "08"}


def test_append_boeth_review_conflict_same_code_no_flag():
    item = {
        "mapped_payload": {"_boeth": {"boeth_code": "01"}},
        "existing_employee_id": "emp-1",
        "review_reasons": [],
    }
    with patch(
        "app.modules.dsn_import.application.boeth_import.boeth_profiles_repository.get_active_by_employee",
        return_value={"company_id": "co-1", "boeth_code": "01"},
    ):
        append_boeth_review_conflict(item, "co-1")
    assert item.get("review_reasons") == []


def test_apply_dsn_boeth_on_commit_creates_profile():
    payload = {
        "_boeth": {
            "boeth_code": "01",
            "valid_from": "2020-01-15",
            "notes": "Import DSN",
        }
    }
    with patch(
        "app.modules.dsn_import.application.boeth_import.boeth_profiles_repository.get_active_by_employee",
        return_value=None,
    ), patch(
        "app.modules.dsn_import.application.boeth_import.save_employee_boeth"
    ) as save_mock:
        warning = apply_dsn_boeth_on_commit("co-1", "emp-1", payload)
    assert warning is None
    save_mock.assert_called_once()


def test_apply_dsn_boeth_on_commit_preserves_manual_profile():
    payload = {"_boeth": {"boeth_code": "01", "valid_from": "2020-01-15"}}
    with patch(
        "app.modules.dsn_import.application.boeth_import.boeth_profiles_repository.get_active_by_employee",
        return_value={"boeth_code": "08"},
    ), patch(
        "app.modules.dsn_import.application.boeth_import.save_employee_boeth"
    ) as save_mock:
        warning = apply_dsn_boeth_on_commit("co-1", "emp-1", payload)
    assert warning is not None
    assert "08" in warning
    save_mock.assert_not_called()


def test_commit_batch_applies_boeth_on_create():
    batch = {"id": "batch-boeth", "status": "previewed", "summary": {}}
    items = [
        {
            "id": "item-e",
            "item_type": "establishment",
            "source_ref": "etab:44306184100047",
            "action": "skip",
            "mapped_payload": {"siret": "44306184100047"},
        },
        {
            "id": "item-emp",
            "item_type": "employee",
            "source_ref": "emp:44306184100047:001",
            "action": "create",
            "mapped_payload": {
                "nir": "180032710123448",
                "first_name": "Jean",
                "last_name": "MARTIN",
                "_boeth": {
                    "boeth_code": "01",
                    "valid_from": "2020-01-15",
                    "notes": "Import DSN",
                },
            },
        },
    ]
    with patch("app.modules.dsn_import.application.commit.repo") as repo, patch(
        "app.modules.dsn_import.application.commit._commit_employee",
        return_value=("emp-new", True, {"id": "emp-new", "company_id": "co-1", "user_id": None}),
    ), patch(
        "app.modules.dsn_import.application.boeth_import.apply_dsn_boeth_on_commit",
        return_value=None,
    ) as boeth_mock:
        repo.get_batch.return_value = batch
        repo.list_items.return_value = items
        commit_batch("batch-boeth")
        boeth_mock.assert_called_once()
