"""Tests ciblés sur le moteur d'obligations (dédup VIP embauche, clés normalisées)."""

from datetime import date

from app.modules.medical_follow_up.infrastructure import obligation_engine as oe


def test_dedupe_key_normalizes_trigger_and_visit_type():
    d = date(2028, 3, 10)
    assert oe._dedupe_key("vip", None, d) == ("vip", "", d.isoformat())
    assert oe._dedupe_key(None, "  embauche  ", d) == ("", "embauche", d.isoformat())


def test_vip_embauche_dedupe_key_must_match_stored_trigger_type():
    """Régression : une clé « periodicite_vip » avec une ligne « embauche » empêchait la dédup."""
    d = date(2031, 6, 1)
    key_embauche = oe._dedupe_key("vip", "embauche", d)
    key_wrong = oe._dedupe_key("vip", "periodicite_vip", d)
    assert key_embauche != key_wrong
    assert key_embauche == ("vip", "embauche", d.isoformat())


def test_dedupe_key_demande_uses_request_date():
    due = date(2028, 1, 1)
    req = date(2028, 2, 1)
    assert oe._dedupe_key("demande", "demande", due, req) == ("demande", "demande", req.isoformat())
