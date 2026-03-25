"""
Tests unitaires du service applicatif company_groups (application/service.py).

Dépendances mockées : company_group_repository, pas d'accès DB.
"""

from unittest.mock import MagicMock, patch


from app.modules.company_groups.application import service

MODULE_SERVICE = "app.modules.company_groups.application.service"


def _make_user(is_super_admin: bool = False, accessible_company_ids=None):
    """Utilisateur mock."""
    user = MagicMock()
    user.is_super_admin = is_super_admin
    if accessible_company_ids is None:
        accessible_company_ids = []
    accs = [MagicMock(company_id=cid) for cid in accessible_company_ids]
    user.accessible_companies = accs
    return user


class TestGetAccessibleCompanyIds:
    """get_accessible_company_ids."""

    def test_super_admin_returns_empty_list(self):
        """Convention : super_admin → [] (pas de filtre, tout accessible)."""
        user = _make_user(is_super_admin=True)
        result = service.get_accessible_company_ids(user)
        assert result == []

    def test_non_super_admin_returns_company_ids_from_accessible_companies(self):
        """Retourne les company_id des accessible_companies."""
        user = _make_user(is_super_admin=False, accessible_company_ids=["c1", "c2"])
        result = service.get_accessible_company_ids(user)
        assert result == ["c1", "c2"]

    def test_accessible_companies_none_treated_as_empty(self):
        """Si accessible_companies est None, traité comme []."""
        user = MagicMock()
        user.is_super_admin = False
        user.accessible_companies = None
        result = service.get_accessible_company_ids(user)
        assert result == []


class TestGetCompanyIdsForGroup:
    """get_company_ids_for_group."""

    def test_returns_empty_when_group_has_no_companies(self):
        """Si le groupe n'a aucune entreprise → []."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = []
        user = _make_user(is_super_admin=False)
        with patch(f"{MODULE_SERVICE}.company_group_repository", mock_repo):
            result = service.get_company_ids_for_group("g1", user)
        assert result == []

    def test_super_admin_gets_all_group_company_ids(self):
        """Super admin reçoit toutes les entreprises du groupe."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = ["c1", "c2", "c3"]
        user = _make_user(is_super_admin=True)
        with patch(f"{MODULE_SERVICE}.company_group_repository", mock_repo):
            result = service.get_company_ids_for_group("g1", user)
        assert result == ["c1", "c2", "c3"]
        mock_repo.get_company_ids_by_group_id.assert_called_once_with("g1")

    def test_non_super_admin_gets_intersection_with_accessible(self):
        """Intersection entre entreprises du groupe et accessible_companies."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = ["c1", "c2", "c3"]
        user = _make_user(is_super_admin=False, accessible_company_ids=["c1", "c3"])
        with patch(f"{MODULE_SERVICE}.company_group_repository", mock_repo):
            result = service.get_company_ids_for_group("g1", user)
        assert result == ["c1", "c3"]


class TestGetGroupCompanyIdsForPermissionCheck:
    """get_group_company_ids_for_permission_check."""

    def test_delegates_to_repository(self):
        """Délègue au repository get_group_company_ids_for_permission_check."""
        mock_repo = MagicMock()
        mock_repo.get_group_company_ids_for_permission_check.return_value = [
            "c1",
            "c2",
        ]
        with patch(f"{MODULE_SERVICE}.company_group_repository", mock_repo):
            result = service.get_group_company_ids_for_permission_check("g1")
        assert result == ["c1", "c2"]
        mock_repo.get_group_company_ids_for_permission_check.assert_called_once_with(
            "g1"
        )


class TestFilterCompaniesByAccess:
    """filter_companies_by_access."""

    def test_empty_accessible_returns_all_companies(self):
        """Si accessible_company_ids vide (ex. super_admin), retourne toute la liste."""
        companies = [
            {"id": "c1", "company_name": "C1"},
            {"id": "c2", "company_name": "C2"},
        ]
        result = service.filter_companies_by_access(companies, [])
        assert result == companies

    def test_filters_by_accessible_ids(self):
        """Ne conserve que les entreprises dont l'id est dans accessible_company_ids."""
        companies = [
            {"id": "c1", "company_name": "C1"},
            {"id": "c2", "company_name": "C2"},
            {"id": "c3", "company_name": "C3"},
        ]
        result = service.filter_companies_by_access(companies, ["c1", "c3"])
        assert len(result) == 2
        assert result[0]["id"] == "c1"
        assert result[1]["id"] == "c3"

    def test_company_without_id_excluded(self):
        """Une entrée sans clé 'id' n'est pas incluse (c.get('id') in acc_set)."""
        companies = [
            {"id": "c1", "company_name": "C1"},
            {"company_name": "Sans id"},
        ]
        result = service.filter_companies_by_access(companies, ["c1"])
        assert len(result) == 1
        assert result[0]["id"] == "c1"
