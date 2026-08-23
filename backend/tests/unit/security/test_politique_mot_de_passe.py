"""
Une seule politique de mot de passe pour tous les chemins.

Audit Axe A : l'activation exige 8 caractères + majuscule + minuscule +
chiffre, mais la réinitialisation et le changement de mot de passe
acceptaient n'importe quelle chaîne (`new_password: str`, sans contrainte).
Un salarié pouvait donc contourner la politique en passant par
« mot de passe oublié » — la barrière la plus haute ne sert à rien si une
porte à côté est ouverte.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.activation.domain.rules import validate_activation_password

MOTS_DE_PASSE_REFUSES = [
    ("court", "Aa1"),
    ("sans majuscule", "motdepasse1"),
    ("sans minuscule", "MOTDEPASSE1"),
    ("sans chiffre", "MotDePasse"),
    ("vide", ""),
]
MOT_DE_PASSE_CONFORME = "MotDePasse1"


class TestRegleCommune:
    @pytest.mark.parametrize("cas,valeur", MOTS_DE_PASSE_REFUSES)
    def test_la_regle_de_reference_refuse(self, cas, valeur):
        assert validate_activation_password(valeur) is not None, cas

    def test_la_regle_de_reference_accepte_un_mot_de_passe_conforme(self):
        assert validate_activation_password(MOT_DE_PASSE_CONFORME) is None


class TestResetEtChangement:
    """Les schémas de reset et de changement appliquent la MÊME règle."""

    def _schemas(self):
        from app.modules.auth.schemas.requests import (
            PasswordChange,
            PasswordResetConfirm,
        )

        return [
            (
                "reset",
                lambda mdp: PasswordResetConfirm(token="jeton", new_password=mdp),
            ),
            (
                "change",
                lambda mdp: PasswordChange(
                    current_password="AncienMdp1", new_password=mdp
                ),
            ),
        ]

    @pytest.mark.parametrize("cas,valeur", MOTS_DE_PASSE_REFUSES)
    def test_mot_de_passe_faible_refuse_partout(self, cas, valeur):
        for nom, construire in self._schemas():
            with pytest.raises(ValidationError):
                construire(valeur)

    def test_mot_de_passe_conforme_accepte_partout(self):
        for nom, construire in self._schemas():
            construire(MOT_DE_PASSE_CONFORME)  # ne lève pas


class TestConnexionNonImpactee:
    """La règle porte sur le CHANGEMENT de mot de passe, jamais sur la
    connexion : les ~245 comptes existants, dont beaucoup ont un mot de
    passe antérieur à la règle, doivent continuer à se connecter."""

    def test_le_schema_de_connexion_n_applique_pas_la_regle(self):
        from app.modules.auth.api import router

        source = router.login_route.__doc__ or ""
        assert source is not None  # la route existe
        # La connexion utilise le formulaire OAuth2 standard, qui ne porte
        # aucun validateur de robustesse — sinon un compte légitime au
        # mot de passe ancien serait enfermé dehors.
        import inspect

        signature = inspect.signature(router.login_route)
        annotation = str(signature.parameters["form_data"].annotation)
        assert "OAuth2PasswordRequestForm" in annotation

    def test_un_ancien_mot_de_passe_reste_accepte_a_la_connexion(self):
        """Un mot de passe non conforme ne doit PAS être rejeté au login."""
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        from app.main import app

        with patch("app.modules.auth.api.router.login") as connexion:
            connexion.return_value = {"access_token": "jeton", "token_type": "bearer"}
            reponse = TestClient(app, raise_server_exceptions=False).post(
                "/api/auth/login",
                data={"username": "salarie@exemple.fr", "password": "ancien"},
            )
        # 422 signifierait que la règle de robustesse bloque la connexion.
        assert reponse.status_code != 422
        # Et surtout : la requête a bien ATTEINT le handler d'authentification.
        connexion.assert_called_once_with("salarie@exemple.fr", "ancien")
