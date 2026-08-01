"""Garde-fou : une relance d'échéance RH ne part qu'aux accès actifs joignables.

Deux silences étaient possibles, tous deux invisibles côté RH.

1. Un accès révoqué restait destinataire : `fetch_company_users_rows` ne filtre pas
   `is_active` (l'écran d'administration doit continuer à voir les accès révoqués).
   Le doublon d'import DSN de Vanessa, révoqué sur les sept sociétés, figurait encore
   dans la liste d'envoi.
2. Une adresse fabriquée (`@eywai.access.local`, `.dsn-import.local`) passait le test
   `if email and "@" in email`. L'envoi échouait côté SMTP, `require_delivery=False`
   absorbait l'échec, et l'on croyait avoir prévenu quelqu'un qui n'a jamais rien reçu.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.notifications.application import hr_deadline_reminders as mod

pytestmark = pytest.mark.unit


def _row(user_id: str, role: str, is_active: bool = True) -> dict:
    return {"user_id": user_id, "role": role, "is_active": is_active}


def _recipients(rows: list[dict], emails: dict[str, str]) -> list[str]:
    with patch.object(mod, "fetch_company_users_rows", return_value=rows), patch.object(
        mod, "get_user_email", side_effect=lambda uid: emails.get(uid)
    ):
        return mod.fetch_rh_recipient_emails("company-1")


def test_acces_revoque_exclu():
    """Un accès is_active=False ne reçoit plus rien, même avec une adresse réelle."""
    rows = [_row("u1", "admin", is_active=False), _row("u2", "rh")]
    emails = {"u1": "doublon@exemple.fr", "u2": "vraie@exemple.fr"}

    assert _recipients(rows, emails) == ["vraie@exemple.fr"]


def test_acces_actif_conserve_si_is_active_absent():
    """Absence de la colonne (base non migrée) ne doit pas couper les envois."""
    rows = [{"user_id": "u1", "role": "rh"}]

    assert _recipients(rows, {"u1": "vraie@exemple.fr"}) == ["vraie@exemple.fr"]


@pytest.mark.parametrize(
    "adresse",
    [
        "gaelle.bouali@eywai.access.local",
        "import.vanessa.amate.383122@534386495.dsn-import.local",
        "quelquun@dsn-import.eywai.fr",
    ],
)
def test_adresse_fabriquee_exclue(adresse: str):
    """Une adresse fabriquée identifie un compte, elle ne joint personne."""
    rows = [_row("u1", "rh")]

    assert _recipients(rows, {"u1": adresse}) == []


def test_adresse_fabriquee_journalisee():
    """Le silence doit être visible : l'adresse écartée est nommée dans le log.

    On vérifie l'appel plutôt que le texte capturé : le logger applicatif ne propage
    pas vers la racine, `caplog` ne le verrait donc pas.
    """
    rows = [_row("u1", "rh"), _row("u2", "admin")]
    emails = {"u1": "gaelle.bouali@eywai.access.local", "u2": "vraie@exemple.fr"}

    with patch.object(mod.logger, "warning") as warn:
        assert _recipients(rows, emails) == ["vraie@exemple.fr"]

    warn.assert_called_once()
    assert "gaelle.bouali@eywai.access.local" in warn.call_args.args


def test_role_non_rh_exclu():
    """Seuls admin, rh et collaborateur_rh sont destinataires."""
    rows = [_row("u1", "collaborateur"), _row("u2", "custom"), _row("u3", "rh")]
    emails = {"u1": "a@exemple.fr", "u2": "b@exemple.fr", "u3": "c@exemple.fr"}

    assert _recipients(rows, emails) == ["c@exemple.fr"]


def test_doublons_normalises():
    """Deux accès du même compte sur la même société ne donnent qu'un destinataire."""
    rows = [_row("u1", "rh"), _row("u1", "admin")]

    assert _recipients(rows, {"u1": "Vraie@Exemple.FR"}) == ["vraie@exemple.fr"]
