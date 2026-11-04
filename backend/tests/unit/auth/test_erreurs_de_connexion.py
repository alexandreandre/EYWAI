"""Connexion : un statut et un code par cas, sans jamais dire si un compte existe.

Avant, tout échec rendait 400 « Identifiant ou mot de passe incorrect » : trop
de tentatives, panne du service d'authentification, base injoignable, adresse
non confirmée, et même un bug. Le front (frontend/src/lib/messageEchecConnexion.ts)
attend déjà 429, 403, 503 et 5xx. Tant que le mot de passe n'est pas vérifié,
la réponse reste la même pour un compte inconnu, un mauvais mot de passe et un
compte bloqué : Supabase Auth dit « User is banned » avant de vérifier le mot
de passe, le distinguer révélerait que l'adresse a un compte.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi import HTTPException
from supabase_auth.errors import AuthApiError, AuthInvalidCredentialsError, AuthRetryableError

from app.modules.auth.application import service
from app.modules.auth.application.service import login

pytestmark = pytest.mark.unit

SESSION = {"access_token": "jeton", "refresh_token": "r", "expires_in": 3600, "expires_at": 1}
AVEC_ACCES = SimpleNamespace(is_platform_admin=False, accessible_companies=["societe"])


def _refus(*, connexion=None, compte=AVEC_ACCES, resolution=None, identifiant="salarie@exemple.fr"):
    with (
        patch.object(service, "auth_provider") as auth,
        patch.object(service, "user_from_token") as jeton,
        patch.object(service, "user_resolver") as resolveur,
    ):
        if connexion is not None:
            auth.sign_in_with_password.side_effect = connexion
        else:
            auth.sign_in_with_password.return_value = SESSION
        jeton.get_user.return_value = compte
        if isinstance(resolution, Exception):
            resolveur.resolve_email.side_effect = resolution
        else:
            resolveur.resolve_email.return_value = resolution
        with pytest.raises(HTTPException) as refus:
            login(identifiant, "mot-de-passe")
    return refus.value.status_code, refus.value.detail


INCORRECTS = (400, {"code": "identifiants_incorrects", "message": "Identifiant ou mot de passe incorrect"})


def test_mauvais_mot_de_passe():
    assert _refus(connexion=AuthApiError("Invalid login credentials", 400, "invalid_credentials")) == INCORRECTS


def test_identifiant_inconnu_meme_reponse():
    assert _refus(identifiant="pseudo-inconnu", resolution=None) == INCORRECTS


def test_compte_bloque_meme_reponse_qu_un_compte_inconnu():
    """Supabase répond « User is banned » avant de vérifier le mot de passe."""
    assert _refus(connexion=AuthApiError("User is banned", 400, "user_banned")) == INCORRECTS


def test_champ_refuse_par_le_client_supabase():
    assert _refus(connexion=AuthInvalidCredentialsError("You must provide a password")) == INCORRECTS


def test_trop_de_tentatives():
    statut, detail = _refus(connexion=AuthApiError("Request rate limit reached", 429, "over_request_rate_limit"))
    assert (statut, detail["code"]) == (429, "trop_de_tentatives")
    assert "Patientez" in detail["message"]


@pytest.mark.parametrize(
    "panne",
    [
        AuthRetryableError("Bad gateway", 502),
        httpx.ConnectError("connexion refusée"),
        AuthApiError("Database error querying schema", 500, "unexpected_failure"),
    ],
)
def test_service_d_authentification_injoignable(panne):
    statut, detail = _refus(connexion=panne)
    assert (statut, detail["code"]) == (503, "service_indisponible")
    assert "mot de passe n'est pas en cause" in detail["message"]


def test_base_injoignable_pendant_la_resolution_de_l_identifiant():
    statut, detail = _refus(identifiant="pseudo", resolution=httpx.ReadTimeout("délai"))
    assert (statut, detail["code"]) == (503, "service_indisponible")


def test_adresse_non_confirmee_dite_apres_le_mot_de_passe():
    statut, detail = _refus(connexion=AuthApiError("Email not confirmed", 400, "email_not_confirmed"))
    assert (statut, detail["code"]) == (400, "email_non_confirmee")


def test_compte_sans_aucun_acces_dit_desactive_une_fois_le_mot_de_passe_verifie():
    statut, detail = _refus(compte=SimpleNamespace(is_platform_admin=False, accessible_companies=[]))
    assert (statut, detail["code"]) == (403, "compte_desactive")
    assert "Identifiant ou mot de passe incorrect" not in detail["message"]


def test_administrateur_de_la_plateforme_sans_acces_societe_se_connecte():
    with (
        patch.object(service, "auth_provider") as auth,
        patch.object(service, "user_from_token") as jeton,
    ):
        auth.sign_in_with_password.return_value = SESSION
        jeton.get_user.return_value = SimpleNamespace(is_platform_admin=True, accessible_companies=[])
        assert login("admin@exemple.fr", "mdp")["access_token"] == "jeton"


def test_un_bug_n_est_pas_un_mot_de_passe_incorrect():
    statut, detail = _refus(identifiant="pseudo", resolution=KeyError("email"))
    assert (statut, detail["code"]) == (500, "connexion_impossible")


def test_la_route_rend_le_code_et_le_message():
    from fastapi.testclient import TestClient

    from app.main import app

    with patch.object(service, "auth_provider") as auth:
        auth.sign_in_with_password.side_effect = AuthApiError(
            "Request rate limit reached", 429, "over_request_rate_limit"
        )
        reponse = TestClient(app, raise_server_exceptions=False).post(
            "/api/auth/login", data={"username": "salarie@exemple.fr", "password": "x"}
        )
    assert reponse.status_code == 429
    assert reponse.json()["detail"]["code"] == "trop_de_tentatives"
