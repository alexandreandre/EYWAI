"""
Accès RH des rôles `custom`.

Un rôle `custom` n'a pas de droits par son nom : ils viennent de ses permissions.
``User.has_rh_access_in_company`` renvoyait ``False`` pour lui en toutes
circonstances, en laissant à l'appelant le soin de compléter le contrôle — ce
que 123 appels sur 127 oubliaient. Les cinq comptes concernés en production
(directeurs et responsables de sites) ont pourtant 100 % de permissions de
niveau RH.

Ces tests fixent le comportement attendu AVANT le correctif : ils échouent sur
le code d'origine et passent une fois l'accès RH résolu à la construction de
l'utilisateur.
"""

import pytest

from app.modules.users.schemas.responses import CompanyAccess, User


pytestmark = pytest.mark.unit


def _utilisateur(role: str, *, has_rh_permissions=None, company_id="c1") -> User:
    acces = CompanyAccess(
        company_id=company_id,
        company_name="Société",
        role=role,
        is_primary=True,
    )
    if has_rh_permissions is not None:
        acces.has_rh_permissions = has_rh_permissions
    return User(
        id="u1",
        email="u1@exemple.fr",
        first_name="Test",
        last_name="Utilisateur",
        accessible_companies=[acces],
        active_company_id=company_id,
    )


class TestRolesHistoriques:
    """Le correctif ne doit rien changer pour les rôles nommés."""

    @pytest.mark.parametrize("role", ["admin", "rh", "collaborateur_rh"])
    def test_roles_rh_ont_acces(self, role):
        assert _utilisateur(role).has_rh_access_in_company("c1") is True

    def test_collaborateur_na_pas_acces(self):
        assert _utilisateur("collaborateur").has_rh_access_in_company("c1") is False

    def test_autre_entreprise_refusee(self):
        assert _utilisateur("admin").has_rh_access_in_company("autre") is False


class TestRoleCustom:
    """Le cœur du correctif : le rôle custom est jugé sur ses permissions."""

    def test_custom_avec_permissions_rh_a_acces(self):
        utilisateur = _utilisateur("custom", has_rh_permissions=True)
        assert utilisateur.has_rh_access_in_company("c1") is True

    def test_custom_sans_permission_rh_est_refuse(self):
        utilisateur = _utilisateur("custom", has_rh_permissions=False)
        assert utilisateur.has_rh_access_in_company("c1") is False

    def test_custom_non_resolu_est_refuse(self):
        """Fail-closed. Si l'accès RH n'a pas été résolu à la construction, on
        refuse : mieux vaut un refus visible qu'une autorisation par défaut."""
        utilisateur = _utilisateur("custom")
        assert utilisateur.has_rh_access_in_company("c1") is False


class TestAdminPlateforme:
    def test_admin_plateforme_passe_partout(self):
        utilisateur = _utilisateur("collaborateur")
        utilisateur.is_platform_admin = True
        assert utilisateur.has_rh_access_in_company("nimporte") is True


class TestEquivalenceAvecLeControleComplet:
    """`has_rh_access_in_company` doit rester équivalent à
    `can_access_company_as_rh`.

    Le plan prévoyait de router les 123 appels vers `can_access_company_as_rh`.
    Corriger la méthode du modèle produit le MÊME résultat en un seul endroit —
    à condition que les deux ne divergent jamais. Ce test l'interdit : si l'une
    des deux évolue seule, il tombe.
    """

    @pytest.mark.parametrize(
        ("role", "permissions_rh"),
        [
            ("admin", False),
            ("rh", False),
            ("collaborateur_rh", False),
            ("collaborateur", False),
            ("custom", True),
            ("custom", False),
            ("role_inconnu", False),
        ],
    )
    def test_les_deux_controles_donnent_le_meme_verdict(self, role, permissions_rh):
        from unittest.mock import MagicMock, patch

        from app.modules.access_control.application.service import (
            AccessControlService,
        )

        utilisateur = _utilisateur(
            role, has_rh_permissions=permissions_rh if role == "custom" else None
        )
        depot = MagicMock()
        depot.user_has_any_rh_permission.return_value = permissions_rh
        service = AccessControlService(depot)
        with patch.object(
            service, "has_any_rh_permission", return_value=permissions_rh
        ):
            complet = service.can_access_company_as_rh(utilisateur, "c1")
        assert utilisateur.has_rh_access_in_company("c1") == complet
