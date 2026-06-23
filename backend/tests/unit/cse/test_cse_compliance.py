"""Tests unitaires conformité CSE (carence électorale)."""

from datetime import date, timedelta

from app.modules.cse.domain.cse_compliance import compute_cse_compliance


class TestComputeCseCompliance:
    def test_not_required_under_11(self):
        r = compute_cse_compliance(10)
        assert r["cse_ok"] is True
        assert r["cse_status"] == "not_required"
        assert r["cse_obligation"] is False

    def test_obligation_pending_by_default(self):
        r = compute_cse_compliance(13)
        assert r["cse_ok"] is False
        assert r["cse_status"] == "obligation_pending"
        assert r["cse_obligation"] is True

    def test_elected_with_active_members(self):
        r = compute_cse_compliance(13, active_elected_count=2)
        assert r["cse_ok"] is True
        assert r["cse_status"] == "elected"

    def test_carence_valid(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        r = compute_cse_compliance(
            13,
            cse_settings={"cse_status": "carence", "carence_valid_until": future},
        )
        assert r["cse_ok"] is True
        assert r["cse_status"] == "carence"

    def test_carence_expired(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        r = compute_cse_compliance(
            13,
            cse_settings={"cse_status": "carence", "carence_valid_until": past},
        )
        assert r["cse_ok"] is False
        assert r["cse_status"] == "carence_expired"
        assert r["carence_expired"] is True
