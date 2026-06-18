"""Tests des flags needs_review et normalisation éditions preview."""

from pathlib import Path

from app.modules.dsn_import.application.mapping import (
    apply_review_flags,
    build_preview_items,
    compute_review_reasons_from_payload,
    normalize_employee_edits,
)
from app.modules.dsn_import.application.service import revalidate_preview
from app.modules.dsn_import.domain.parser import parse_dsn_files

FIXTURES = Path(__file__).parent / "fixtures"


def _employee_payload(**overrides):
    base = {
        "nir": "180032710123448",
        "salaire_de_base": {"valeur": 2200.0, "type": "mensuel", "a_verifier": False},
    }
    base.update(overrides)
    return base


def test_compute_review_brut_ok():
    reasons = compute_review_reasons_from_payload(_employee_payload())
    assert reasons == []


def test_compute_review_brut_absent():
    reasons = compute_review_reasons_from_payload(
        _employee_payload(salaire_de_base={"valeur": 0, "type": "mensuel"})
    )
    assert reasons == ["brut_absent"]


def test_compute_review_skip_existing_no_brut_flag():
    reasons = compute_review_reasons_from_payload(
        _employee_payload(salaire_de_base={"valeur": 0, "type": "mensuel"}),
        effective_action="skip",
        is_existing=True,
    )
    assert reasons == []


def test_compute_review_nir_incomplet_matricule():
    reasons = compute_review_reasons_from_payload(
        {
            "matricule": "1970879049270",
            "salaire_de_base": {"valeur": 2000.0, "type": "mensuel"},
        }
    )
    assert reasons == ["nir_incomplet"]
    assert "identifiant_absent" not in reasons


def test_apply_review_flags_on_item():
    item = {
        "item_type": "employee",
        "action": "create",
        "is_existing": False,
        "mapped_payload": _employee_payload(salaire_de_base={"valeur": 0, "type": "mensuel"}),
        "preview_columns": {},
    }
    apply_review_flags(item)
    assert item["needs_review"] is True
    assert item["review_reasons"] == ["brut_absent"]
    assert item["preview_columns"]["brut"] == 0


def test_normalize_employee_edits_salaire_brut():
    out = normalize_employee_edits({"salaire_brut": "2500,50"})
    assert out["salaire_de_base"]["valeur"] == 2500.5
    assert out["salaire_de_base"]["a_verifier"] is False
    assert "salaire_brut" not in out


def test_normalize_employee_edits_clears_review_reason():
    item = {
        "item_type": "employee",
        "action": "create",
        "is_existing": False,
        "mapped_payload": _employee_payload(salaire_de_base={"valeur": 0, "type": "mensuel"}),
        "preview_columns": {},
    }
    apply_review_flags(item)
    edits = normalize_employee_edits({"salaire_brut": "3000"})
    item["mapped_payload"].update(edits)
    apply_review_flags(item)
    assert item["needs_review"] is False


def test_build_preview_modern_no_review():
    content = (FIXTURES / "sample_dsn_modern.txt").read_bytes()
    parsed = parse_dsn_files([("sample_dsn_modern.txt", content)])
    items, _ = build_preview_items(parsed)
    emp = next(i for i in items if i["item_type"] == "employee")
    assert emp.get("needs_review") is False
    assert emp.get("review_reasons") == []


def test_revalidate_preview_recomputes_review(monkeypatch):
    batch = {
        "id": "batch-review",
        "status": "previewed",
        "summary": {"import_mode": "onboarding"},
        "preview": {
            "items": [
                {
                    "item_type": "employee",
                    "source_ref": "emp:95147478200020:BERTAUD",
                    "action": "create",
                    "mapped_payload": _employee_payload(
                        salaire_de_base={"valeur": 0, "type": "mensuel"}
                    ),
                    "preview_columns": {"brut": 0},
                    "editable_fields": {},
                }
            ],
            "anomalies": [],
        },
    }

    monkeypatch.setattr(
        "app.modules.dsn_import.application.service.repo.get_batch",
        lambda _bid: batch,
    )
    monkeypatch.setattr(
        "app.modules.dsn_import.application.service.repo.update_batch",
        lambda *_a, **_k: None,
    )

    result = revalidate_preview(
        "batch-review",
        payload_edits={"emp:95147478200020:BERTAUD": {"salaire_brut": "2800"}},
    )
    emp = next(i for i in result["items"] if i["item_type"] == "employee")
    assert emp["needs_review"] is False
    assert result["summary"]["review_summary"]["total"] == 0
