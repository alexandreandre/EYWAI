"""Connexion par lien, sans mot de passe : usage unique, échéance, aucune adresse révélée."""

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
    def __init__(self, reponses=None):
        self.reponses, self.appels = reponses or {}, []

    def table(self, nom):
        return _Table(self, nom)


def test_creer_lien_ne_garde_que_l_empreinte():
    c = _Client()
    jeton = liens.creer_lien("u-1", "invitation", liens.DUREE_INVITATION, c)
    (_, op, donnees, _), = c.appels
    assert op == "insert"
    assert donnees["jeton_hash"] == liens.empreinte(jeton) != jeton
    assert jeton not in str(donnees)
    assert donnees["user_id"] == "u-1" and donnees["origine"] == "invitation"


def test_url_du_lien():
    assert liens.url_du_lien("https://site/", "abc") == "https://site/connexion?jeton=abc"


def test_consommer_un_lien_valable():
    c = _Client({("liens_de_connexion", "update"): [{"user_id": "u-1"}]})
    assert liens.consommer_lien("jeton", c) == "u-1"
    (_, op, donnees, filtres), = c.appels
    assert op == "update" and "used_at" in donnees
    # Une seule mise à jour conditionnelle : pas servi, pas expiré, bonne empreinte.
    assert ("is", "used_at", "null") in filtres
    assert ("eq", "jeton_hash", liens.empreinte("jeton")) in filtres
    assert any(f[0] == "gt" and f[1] == "expires_at" for f in filtres)


@pytest.mark.parametrize("jeton", ["", "x" * 201, "inconnu-servi-ou-expire"])
def test_un_lien_inconnu_servi_ou_expire_est_refuse(jeton):
    with pytest.raises(liens.LienInvalide):
        liens.consommer_lien(jeton, _Client())


def test_le_refus_d_un_lien_dit_pourquoi():
    with patch.object(liens, "consommer_lien", side_effect=liens.LienInvalide("x")):
        with pytest.raises(HTTPException) as exc:
            service.ouvrir_lien_de_connexion("jeton")
    assert exc.value.status_code == 400
    assert exc.value.detail == {"code": liens.CODE_LIEN_INVALIDE, "message": liens.MESSAGE_LIEN_INVALIDE}


def test_demande_pour_un_compte_avec_acces():
    c = _Client({("user_company_accesses", "select"): [{"company_id": "co"}]})
    envois = []
    with patch("app.modules.auth.infrastructure.auth_provider.find_user_id_by_email", return_value="u-1"):
        r = liens.demander_lien(" Quelqu.Un@Exemple.fr ", envoyer=lambda **k: envois.append(k), client=c)
    assert r == {"message": liens.MESSAGE_DEMANDE}
    (envoi,) = envois
    assert envoi["to_email"] == "quelqu.un@exemple.fr"
    inseres = [a for a in c.appels if a[1] == "insert"]
    assert inseres[0][2]["jeton_hash"] == liens.empreinte(envoi["jeton"])
    assert inseres[0][2]["origine"] == "demande"


@pytest.mark.parametrize("compte,acces", [(None, []), ("u-1", [])])
def test_demande_sans_compte_ou_sans_acces_meme_reponse_rien_envoye(compte, acces):
    c = _Client({("user_company_accesses", "select"): acces})
    envois = []
    with patch("app.modules.auth.infrastructure.auth_provider.find_user_id_by_email", return_value=compte):
        r = liens.demander_lien("a@b.fr", envoyer=lambda **k: envois.append(k), client=c)
    assert r == {"message": liens.MESSAGE_DEMANDE}
    assert envois == []
    assert not [a for a in c.appels if a[1] == "insert"]


def test_demande_en_panne_meme_reponse():
    with patch("app.modules.auth.infrastructure.auth_provider.find_user_id_by_email", side_effect=RuntimeError):
        assert liens.demander_lien("a@b.fr", envoyer=lambda **k: None, client=_Client()) == {
            "message": liens.MESSAGE_DEMANDE
        }


def test_ouvrir_un_lien_ouvre_la_session():
    moi = SimpleNamespace(is_platform_admin=False, accessible_companies=["co"])
    session = {"access_token": "acc", "refresh_token": "ref", "expires_in": 3600, "expires_at": 1}
    with patch.object(liens, "consommer_lien", return_value="u-1") as consommer, \
         patch.object(liens, "session_du_compte", return_value=session) as ouvrir, \
         patch.object(service.user_from_token, "get_user", return_value=moi):
        r = service.ouvrir_lien_de_connexion("jeton")
    consommer.assert_called_once_with("jeton")
    ouvrir.assert_called_once_with("u-1")
    assert r["access_token"] == "acc" and r["refresh_token"] == "ref" and r["user"] is moi


def test_ouvrir_un_lien_d_un_compte_sans_acces_est_refuse():
    moi = SimpleNamespace(is_platform_admin=False, accessible_companies=[])
    with patch.object(liens, "consommer_lien", return_value="u-1"), \
         patch.object(liens, "session_du_compte", return_value={"access_token": "acc"}), \
         patch.object(service.user_from_token, "get_user", return_value=moi):
        with pytest.raises(HTTPException) as exc:
            service.ouvrir_lien_de_connexion("jeton")
    assert exc.value.status_code == 403


def test_les_routes_existent():
    from app.modules.auth.api.router import router

    chemins = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
    assert ("/lien-de-connexion", ("POST",)) in chemins
    assert ("/lien-de-connexion/ouvrir", ("POST",)) in chemins
