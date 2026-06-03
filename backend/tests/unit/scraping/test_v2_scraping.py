"""Tests exhaustifs Scraping v2 (validation humaine, tripwire, citation IA, réparation).

Hermétiques : mocks Supabase / subprocess, pas de DB ni réseau réels.
"""

from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.scraping.api.router import router
from app.modules.users.schemas.responses import User

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_super_admin_user():
    return User(
        id=TEST_USER_ID,
        email="super@test.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _super_admin_dep():
    return {"user_id": TEST_USER_ID, "is_active": True}


def _scraping_client():
    """TestClient minimal (évite import app.main / weasyprint)."""
    from app.core.security import get_current_user
    from app.modules.scraping.api.dependencies import verify_super_admin

    app = FastAPI()
    app.include_router(router)  # prefix déjà /api/scraping sur le router
    app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
    app.dependency_overrides[verify_super_admin] = _super_admin_dep
    return TestClient(app)


# --- emit_orchestrator_result enrichi ---


class TestEmitOrchestratorResultV2:
    def test_emits_v2_metadata_fields(self):
        from core.supabase_io import emit_orchestrator_result

        buf = StringIO()
        with redirect_stdout(buf):
            emit_orchestrator_result(
                scraper="SMIC",
                success=True,
                config_key="smic",
                data={"cas_general": 11.88},
                sources_used=["SMIC.py"],
                decision_case="A",
                sources_agreement=True,
                discrepancies=[{"label": "SMIC.py", "is_ai": False}],
                current_value={"cas_general": 11.65},
                proposed_value={"cas_general": 11.88},
                ai_candidate={"value": 11.88, "citation_url": "https://www.urssaf.fr/x"},
                tier="critical",
                requires_review=True,
            )
        out = json.loads(buf.getvalue().strip())
        assert out["decision_case"] == "A"
        assert out["sources_agreement"] is True
        assert out["tier"] == "critical"
        assert out["requires_review"] is True
        assert out["ai_candidate"]["citation_url"] == "https://www.urssaf.fr/x"
        assert out["current_value"]["cas_general"] == 11.65
        assert out["proposed_value"]["cas_general"] == 11.88


# --- build_standard_payload + citation ---


class TestBuildStandardPayloadCitation:
    def test_uses_last_citation_in_meta(self):
        from core.ai_extractor import build_standard_payload, last_citation

        with patch(
            "core.ai_extractor.last_citation",
            return_value={"url": "https://www.urssaf.fr/smic", "date": "01/06/2026"},
        ):
            payload = build_standard_payload(
                item_id="smic",
                item_type="bareme",
                libelle="SMIC",
                sections_or_valeurs={"cas_general": 11.88},
                generator="SMIC_AI.py",
                source_url="https://fallback.example",
                source_label="URSSAF",
             )
        src = payload["meta"]["source"][0]
        assert src["url"] == "https://www.urssaf.fr/smic"
        assert src["date_doc"] == "01/06/2026"

    def test_rejects_missing_official_citation(self):
        from core.ai_extractor import build_standard_payload

        with patch("core.ai_extractor.last_citation", return_value={"url": "", "date": ""}):
            payload = build_standard_payload(
                item_id="smic",
                item_type="bareme",
                libelle="SMIC",
                sections_or_valeurs={"cas_general": 11.88},
                generator="SMIC_AI.py",
                source_url="https://blog.example.com/smic",
                source_label="Blog",
            )
        assert payload is None

    def test_is_official_citation_url(self):
        from core.ai_extractor import is_official_citation_url

        assert is_official_citation_url("https://www.urssaf.fr/taux")
        assert is_official_citation_url("https://boss.gouv.fr/contenu/abc")
        assert not is_official_citation_url("https://blog-rh.example.com/taux")
        assert not is_official_citation_url("")


# --- tier_for ---


class TestTierFor:
    def test_critical_scrapers(self):
        from scraper_manifest import tier_for

        assert tier_for("SMIC") == "critical"
        assert tier_for("PAS") == "critical"
        assert tier_for("AGIRC-ARRCO") == "critical"

    def test_standard_scrapers(self):
        from scraper_manifest import tier_for

        assert tier_for("CSA") == "standard"
        assert tier_for("CFP") == "standard"

    def test_unknown_defaults_standard(self):
        from scraper_manifest import tier_for

        assert tier_for("INEXISTANT") == "standard"


# --- tripwire ---


class TestTripwire:
    def test_normalize_strips_scripts_and_collapses_whitespace(self):
        from bs4 import BeautifulSoup

        from core.tripwire import content_hash, normalize_page_text

        html = "<html><script>x=1</script><body><p>  SMIC   horaire  </p></body></html>"
        soup = BeautifulSoup(html, "html.parser")
        text = normalize_page_text(soup)
        assert "SMIC horaire" in text
        assert "x=1" not in text
        assert content_hash(text) == content_hash("SMIC horaire")

    def test_collect_urls_primary_and_alternatives(self):
        from core.tripwire import collect_urls

        urls = collect_urls(
            {
                "primary_url": "https://a.fr",
                "alternative_urls": ["https://b.fr", "https://a.fr"],
            }
        )
        assert urls == ["https://a.fr", "https://b.fr"]

    def test_run_tripwire_detects_change_and_creates_alert(self):
        from core.tripwire import run_tripwire_for_source

        supabase = MagicMock()
        # Pas de snapshot précédent
        supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        supabase.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("core.tripwire.fetch_soup") as mock_fetch:
            mock_fetch.return_value = MagicMock(
                get_text=lambda *a, **k: "SMIC 11.88"
            )
            # fetch_soup returns soup - patch normalize path
            from bs4 import BeautifulSoup

            mock_fetch.return_value = BeautifulSoup(
                "<p>SMIC 11.88</p>", "html.parser"
            )
            result = run_tripwire_for_source(
                supabase,
                {
                    "id": "src-1",
                    "source_key": "SMIC",
                    "source_name": "SMIC",
                    "primary_url": "https://urssaf.fr/smic",
                    "is_critical": True,
                },
            )
        assert result["checked"] == 1
        assert len(result["baseline"]) == 1
        assert supabase.table.return_value.insert.called


# --- apply_pending_change ---


class TestApplyPendingChange:
    def test_applies_full_config_and_marks_approved(self):
        from core.apply_pending_change import apply_pending_change

        pending = {
            "id": "p-1",
            "status": "pending",
            "config_key": "smic",
            "persistence_mode": "full",
            "proposed_config_data": {"cas_general": 11.88},
            "source_links": ["https://urssaf.fr"],
        }
        supabase = MagicMock()
        supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = pending
        applied_row = {"id": "pc-new", "version": 2, "config_data": pending["proposed_config_data"]}

        with (
            patch("core.apply_pending_change.init_supabase_client", return_value=supabase),
            patch("core.apply_pending_change.fetch_active_config", return_value={"id": "pc-old", "version": 1, "config_data": {}}),
            patch("core.apply_pending_change.persist_full_config") as mock_persist,
        ):
            code = apply_pending_change("p-1", reviewed_by="admin-1")

        assert code == 0
        mock_persist.assert_called_once()
        update_call = supabase.table.return_value.update.return_value.eq.call_args
        assert update_call is not None

    def test_rejects_already_processed(self):
        from core.apply_pending_change import apply_pending_change

        supabase = MagicMock()
        supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "p-1",
            "status": "approved",
        }
        with patch("core.apply_pending_change.init_supabase_client", return_value=supabase):
            code = apply_pending_change("p-1")
        assert code == 3

    def test_uses_cotisations_persist_mode(self):
        from core.apply_pending_change import apply_pending_change

        pending = {
            "id": "p-2",
            "status": "pending",
            "config_key": "cotisations",
            "persistence_mode": "cotisations",
            "proposed_config_data": {"cotisations": []},
            "source_links": [],
        }
        supabase = MagicMock()
        supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = pending

        with (
            patch("core.apply_pending_change.init_supabase_client", return_value=supabase),
            patch("core.apply_pending_change.fetch_active_config", return_value=None),
            patch("core.apply_pending_change.persist_cotisations") as mock_cot,
            patch("core.apply_pending_change.persist_full_config") as mock_full,
        ):
            code = apply_pending_change("p-2")
        assert code == 0
        mock_cot.assert_called_once()
        mock_full.assert_not_called()


# --- API v2 (router isolé) ---


class TestScrapingV2ApiRoutes:
    def test_list_pending_returns_200(self):
        client = _scraping_client()
        with patch(
            "app.modules.scraping.api.router.queries.list_pending_changes",
            return_value={"pending": [{"id": "p-1", "status": "pending"}], "total": 1},
        ):
            r = client.get("/api/scraping/pending")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_get_pending_returns_404_when_missing(self):
        client = _scraping_client()
        with patch(
            "app.modules.scraping.api.router.queries.get_pending_change",
            side_effect=ValueError("Changement en attente non trouvé"),
        ):
            r = client.get("/api/scraping/pending/p-x")
        assert r.status_code == 404

    def test_approve_pending_returns_200(self):
        client = _scraping_client()
        with patch(
            "app.modules.scraping.api.router.commands.approve_pending_change",
            return_value={"success": True, "pending_id": "p-1", "logs": []},
        ):
            r = client.post(
                "/api/scraping/pending/p-1/approve",
                json={"override_value": None},
            )
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_reject_pending_returns_200(self):
        client = _scraping_client()
        with patch(
            "app.modules.scraping.api.router.commands.reject_pending_change",
            return_value={"success": True, "pending_id": "p-1"},
        ):
            r = client.post(
                "/api/scraping/pending/p-1/reject",
                json={"review_note": "Valeur douteuse"},
            )
        assert r.status_code == 200

    def test_run_tripwire_returns_200(self):
        client = _scraping_client()
        with patch(
            "app.modules.scraping.api.router.commands.run_tripwire",
            return_value={"message": "ok", "sources_count": 3, "job_ids": ["j1"]},
        ):
            r = client.post("/api/scraping/tripwire")
        assert r.status_code == 200
        assert r.json()["sources_count"] == 3

    def test_pending_unauthenticated_returns_401(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/api/scraping/pending")
        assert r.status_code == 401


# --- RateSpec tier field ---


class TestRateSpecTier:
    def test_rate_spec_has_tier_and_source_key_fields(self):
        from scraping.SMIC.spec import SPEC

        assert SPEC.tier is None or SPEC.tier in ("critical", "standard", "static")
        assert hasattr(SPEC, "source_key")

    def test_smic_resolves_critical_via_tier_for(self):
        from scraping.SMIC.spec import SPEC
        from scraper_manifest import tier_for

        effective = SPEC.tier or tier_for(SPEC.scraper_name)
        assert effective == "critical"
