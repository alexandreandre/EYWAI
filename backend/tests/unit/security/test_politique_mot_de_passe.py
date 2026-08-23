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
