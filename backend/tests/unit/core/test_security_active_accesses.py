"""Chargement de session : les accès désactivés ne doivent jamais être accessibles.

Régression : `user_company_accesses.is_active` était écrit par le provisioning
(`deactivate_stale_access`) mais jamais lu par `get_current_user`. Un accès révoqué
restait donc effectif — la révocation n'était que cosmétique.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core import security


class _QueryRecorder:
    """Faux query builder Supabase : enregistre les .eq() appliqués."""

    def __init__(self, rows, store):
        self._rows = rows
        self._store = store

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self._store.append((column, value))
        return self

    def execute(self):
        filtered = self._rows
        for column, value in self._store:
            if column == "is_active":
                filtered = [r for r in filtered if r.get("is_active", True) == value]
        return SimpleNamespace(data=filtered, count=len(filtered))


def _access_row(company_id, name, *, is_active=True):
    return {
        "company_id": company_id,
        "role": "rh",
        "is_primary": company_id == "co-maji",
        "is_active": is_active,
        "companies": {
            "id": company_id,
            "company_name": name,
            "siret": None,
            "logo_url": None,
            "logo_scale": 1.0,
            "group_id": None,
            "company_groups": None,
        },
    }


ACCESS_ROWS = [
    _access_row("co-maji", "MAJI"),
    _access_row("co-z404", "Zone 404 Mars"),
    _access_row("co-mbc", "Mont Blanc Composite", is_active=False),
    _access_row("co-cartol", "Cartol Industrie", is_active=False),
]


def _build_client(access_filters):
    """Client Supabase factice : profils, super_admins et accès multi-entreprises."""
    client = MagicMock()

    def table(name):
        if name == "profiles":
            return _QueryRecorder(
                [{"first_name": "Gaëlle", "last_name": "Bouali",
                  "must_change_password": False}],
                [],
            )
        if name == "super_admins":
            return _QueryRecorder([], [])
        if name == "user_company_accesses":
            return _QueryRecorder(ACCESS_ROWS, access_filters)
        raise AssertionError(f"table inattendue : {name}")

    client.table.side_effect = table
    return client


def _call_get_current_user(access_filters):
    client = _build_client(access_filters)
    auth_user = SimpleNamespace(id="user-gaelle", email="gaelle@example.test")

    with patch.object(security, "get_supabase_admin_client", return_value=client), \
         patch.object(security, "supabase") as mock_supabase, \
         patch.object(security, "_set_session_company", return_value=True), \
         patch.object(security, "execute_with_retry", side_effect=lambda fn: fn()):
        mock_supabase.auth.get_user.return_value = SimpleNamespace(user=auth_user)
        return security.get_current_user(token="jwt", x_active_company=None)


def test_deactivated_accesses_are_excluded_from_session():
    """Un accès is_active=False ne doit pas apparaître dans accessible_companies."""
    user = _call_get_current_user([])

    names = sorted(acc.company_name for acc in user.accessible_companies)
    assert names == ["MAJI", "Zone 404 Mars"], (
        "les accès révoqués (MBC, Cartol) restent accessibles en session"
    )


def test_session_query_filters_on_is_active():
    """Le filtre doit être poussé en base (index idx_uca_user_active)."""
    filters: list[tuple[str, object]] = []
    _call_get_current_user(filters)

    assert ("is_active", True) in filters, (
        "la requête user_company_accesses ne filtre pas sur is_active"
    )


def test_active_company_never_falls_back_to_a_revoked_access():
    """L'entreprise active ne doit jamais être choisie parmi les accès révoqués."""
    user = _call_get_current_user([])

    revoked = {"co-mbc", "co-cartol"}
    assert user.active_company_id not in revoked
    assert user.active_company_id == "co-maji"


@pytest.mark.parametrize("requested", ["co-mbc", "co-cartol"])
def test_x_active_company_on_revoked_access_is_ignored(requested):
    """En-tête X-Active-Company pointant un accès révoqué : ignoré, pas honoré."""
    client = _build_client([])
    auth_user = SimpleNamespace(id="user-gaelle", email="gaelle@example.test")

    with patch.object(security, "get_supabase_admin_client", return_value=client), \
         patch.object(security, "supabase") as mock_supabase, \
         patch.object(security, "_set_session_company", return_value=True), \
         patch.object(security, "execute_with_retry", side_effect=lambda fn: fn()):
        mock_supabase.auth.get_user.return_value = SimpleNamespace(user=auth_user)
        user = security.get_current_user(token="jwt", x_active_company=requested)

    assert user.active_company_id != requested
