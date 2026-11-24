"""Lien d'invitation : la personne crée son mot de passe ; le lien sert une fois, avant son échéance."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.auth.application import liens_de_connexion as liens
from app.modules.auth.application import service


class _Table:
    def __init__(self, base, nom):
        self.base, self.nom, self.op, self.filtres, self.donnees = base, nom, "select", [], None

    def select(self, *_a, **_k):
        return self

    def insert(self, donnees):
        self.op, self.donnees = "insert", donnees
        return self

    def update(self, donnees):
        self.op, self.donnees = "update", donnees
        return self

    def eq(self, col, val):
        self.filtres.append(("eq", col, val))
        return self

    def is_(self, col, val):
        self.filtres.append(("is", col, val))
        return self

    def gt(self, col, val):
        self.filtres.append(("gt", col, val))
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        self.base.appels.append((self.nom, self.op, self.donnees, list(self.filtres)))
        return SimpleNamespace(data=self.base.reponses.get((self.nom, self.op), []))


class _Client:
    def __init__(self, reponses=None, email="p@exemple.fr"):
        self.reponses, self.appels = reponses or {}, []
        self.auth = SimpleNamespace(admin=SimpleNamespace(
            get_user_by_id=lambda uid: SimpleNamespace(user=SimpleNamespace(email=email))
        ))

    def table(self, nom):
        return _Table(self, nom)


def _valable(filtres):
    return ("is", "used_at", "null") in filtres and any(f[0] == "gt" and f[1] == "expires_at" for f in filtres)


def test_creer_lien_ne_garde_que_l_empreinte():
    c = _Client()
    jeton = liens.creer_lien("u-1", "invitation", liens.DUREE_INVITATION, c)
    (_, op, donnees, _), = c.appels
    assert op == "insert"
    assert donnees["jeton_hash"] == liens.empreinte(jeton) != jeton
    assert jeton not in str(donnees)


def test_url_du_lien():
    assert liens.url_du_lien("https://site/", "abc") == "https://site/connexion?jeton=abc"


def test_verifier_un_lien_ne_le_consomme_pas():
    c = _Client({("liens_de_connexion", "select"): [{"user_id": "u-1"}],
                 ("profiles", "select"): [{"first_name": "Prénom"}]})
    assert liens.verifier_lien("jeton", c) == {"valide": True, "prenom": "Prénom", "email": "p@exemple.fr"}
    assert all(op == "select" for (_, op, _, _) in c.appels)
    assert _valable(c.appels[0][3])


@pytest.mark.parametrize("jeton", ["", "x" * 201, "servi-ou-expire"])
def test_verifier_un_lien_servi_ou_expire(jeton):
    assert liens.verifier_lien(jeton, _Client()) == {"valide": False, "prenom": None, "email": None}


def test_consommer_un_lien_valable():
    c = _Client({("liens_de_connexion", "update"): [{"user_id": "u-1"}]})
    assert liens.consommer_lien("jeton", c) == "u-1"
    (_, op, donnees, filtres), = c.appels
    assert op == "update" and "used_at" in donnees
    assert ("eq", "jeton_hash", liens.empreinte("jeton")) in filtres
    assert _valable(filtres)


@pytest.mark.parametrize("jeton", ["", "x" * 201, "inconnu-servi-ou-expire"])
def test_consommer_un_lien_inconnu_servi_ou_expire(jeton):
    with pytest.raises(liens.LienInvalide):
        liens.consommer_lien(jeton, _Client())


MOI = SimpleNamespace(is_platform_admin=False, accessible_companies=["co"])
SESSION = {"access_token": "acc", "refresh_token": "ref", "expires_in": 3600, "expires_at": 1}


def test_activer_une_invitation():
    with patch.object(liens, "compte_du_lien", return_value="u-1"), \
         patch.object(liens, "consommer_lien", return_value="u-1") as consommer, \
         patch.object(liens, "email_du_compte", return_value="p@exemple.fr"), \
         patch.object(service.auth_provider, "update_user_password") as poser, \
         patch.object(service.auth_provider, "sign_in_with_password", return_value=SESSION) as connecter, \
         patch.object(service.user_from_token, "get_user", return_value=MOI):
        r = service.activer_invitation("jeton", "Motdepasse1")
    poser.assert_called_once_with("u-1", "Motdepasse1")
    consommer.assert_called_once_with("jeton")
    connecter.assert_called_once_with("p@exemple.fr", "Motdepasse1")
    assert r["access_token"] == "acc" and r["user"] is MOI


def test_un_mot_de_passe_refuse_ne_grille_pas_le_lien():
    with patch.object(liens, "compte_du_lien", return_value="u-1"), \
         patch.object(liens, "consommer_lien") as consommer, \
         patch.object(service.auth_provider, "update_user_password") as poser:
        with pytest.raises(HTTPException) as exc:
            service.activer_invitation("jeton", "court")
    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "mot_de_passe_invalide"
    poser.assert_not_called()
    consommer.assert_not_called()


def test_un_lien_servi_ou_expire_ne_pose_aucun_mot_de_passe():
    with patch.object(liens, "compte_du_lien", return_value=None), \
         patch.object(service.auth_provider, "update_user_password") as poser:
        with pytest.raises(HTTPException) as exc:
            service.activer_invitation("jeton", "Motdepasse1")
    assert exc.value.detail == {"code": liens.CODE_LIEN_INVALIDE, "message": liens.MESSAGE_LIEN_INVALIDE}
    poser.assert_not_called()


def test_les_routes():
    from app.modules.auth.api.router import router

    chemins = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
    assert ("/lien-de-connexion/verifier", ("POST",)) in chemins
    assert ("/lien-de-connexion/activer", ("POST",)) in chemins
    # Plus de connexion sans mot de passe ni de lien demandé par e-mail.
    assert not {p for p, _ in chemins} & {"/lien-de-connexion", "/lien-de-connexion/ouvrir"}
