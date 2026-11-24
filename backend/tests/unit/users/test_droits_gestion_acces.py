"""Droits sur la gestion des accès : on ne donne, ne change ni ne retire plus que ce qu'on a.

Relecture de sécurité du 24/11 : `POST /api/users/grant-access` (par adresse) laissait
une RH de la société A rattacher à A n'importe quel compte de la base, avec le rôle
`rh` ou `admin`, écrasait un accès existant (y compris coupé par un super-admin) et
disait si une adresse avait un compte. Règles appliquées, mêmes pour toutes les routes
de gestion d'accès :

1. hiérarchie : on ne donne qu'un rôle que `check_role_hierarchy` permet (strictement
   inférieur au sien ; une RH ne fait ni RH ni admin, un admin ne fait pas d'admin) ;
2. personne ne touche à son propre accès par ces routes ;
3. on n'agit que sur une personne qu'on gère déjà : elle a un accès actif dans une
   société de l'appelant, avec un rôle que l'appelant peut modifier ;
4. pas d'écrasement : un accès existant (actif ou coupé) n'est jamais réécrit par un
   octroi ;
5. pas d'énumération : hors super-admin, une adresse inconnue et une adresse d'une
   personne qu'on ne gère pas reçoivent la même réponse ;
6. les droits fins (`custom`) : on ne donne pas une permission d'un niveau au-dessus
   du sien, ni à soi-même.

Les routes tournent ici sur une petite base en mémoire.
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.consultation import permis_en_consultation
from app.core.security import get_current_user
from app.modules.users.schemas.responses import CompanyAccess, User

pytestmark = pytest.mark.unit

def _id(nom: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"martine-test/{nom}"))


CO_A = _id("co-a")
CO_B = _id("co-b")
CO_Z = _id("co-z")  # société d'un autre client
RH_A = _id("rh-a")
COLLAB_RH_A = _id("collab-rh-a")
ADMIN_GROUPE = _id("admin-groupe")
ADMIN2_GROUPE = _id("admin2-groupe")
CIBLE = _id("cible")
ETRANGER = _id("etranger")
INEXISTANT = _id("inexistant")
P_COLLAB = _id("p-collab")
P_RH = _id("p-rh")
P_BANQUE = _id("p-banque")
P_LIBRE = _id("p-libre")
P_INCONNUE = _id("p-inconnue")
TPL_COMMUN_RH = _id("tpl-commun-rh")
TPL_GESTION_PAIE = _id("tpl-gestion-paie")
TPL_SOCIETE_Z = _id("tpl-societe-z")


# --------------------------------------------------------------------------- base


class _Base:
    def __init__(self):
        self.companies = {CO_A: "Société A", CO_B: "Société B", CO_Z: "Société Z"}
        self.emails = {
            "rh@a.fr": RH_A,
            "collab-rh@a.fr": COLLAB_RH_A,
            "admin@groupe.fr": ADMIN_GROUPE,
            "admin2@groupe.fr": ADMIN2_GROUPE,
            "cible@a.fr": CIBLE,
            "etranger@z.fr": ETRANGER,
        }
        self.profiles = {uid: {"id": uid} for uid in self.emails.values()}
        self.accesses = [
            self._a(RH_A, CO_A, "rh"),
            self._a(COLLAB_RH_A, CO_A, "collaborateur_rh"),
            self._a(ADMIN_GROUPE, CO_A, "admin"),
            self._a(ADMIN_GROUPE, CO_B, "admin"),
            self._a(ADMIN2_GROUPE, CO_A, "admin"),
            self._a(CIBLE, CO_A, "collaborateur"),
            self._a(ETRANGER, CO_Z, "rh"),
        ]
        self.permissions = {
            P_COLLAB: "collaborateur",
            P_RH: "rh",
            P_BANQUE: "admin",
            P_LIBRE: None,
        }
        self.user_permissions: dict[tuple[str, str], set[str]] = {}
        self.templates = {
            TPL_COMMUN_RH: {"company_id": None, "permissions": [P_RH, P_LIBRE]},
            TPL_GESTION_PAIE: {"company_id": None, "permissions": [P_RH, P_BANQUE]},
            TPL_SOCIETE_Z: {"company_id": CO_Z, "permissions": [P_LIBRE]},
        }

    @staticmethod
    def _a(user_id, company_id, role, **extra):
        return {
            "user_id": user_id,
            "company_id": company_id,
            "role": role,
            "is_primary": False,
            "is_active": True,
            "lecture_seule": False,
            **extra,
        }

    def find(self, user_id, company_id) -> dict | None:
        return next(
            (
                a
                for a in self.accesses
                if a["user_id"] == user_id and a["company_id"] == company_id
            ),
            None,
        )


class _UserRepo:
    def __init__(self, base: _Base):
        self.b = base

    def get_by_id(self, user_id):
        return self.b.profiles.get(user_id)

    def get_by_email(self, email):
        uid = self.b.emails.get(email)
        return {"id": uid, "email": email} if uid else None


class _AccessRepo:
    def __init__(self, base: _Base):
        self.b = base

    def get_by_user_and_company(self, user_id, company_id):
        a = self.b.find(user_id, company_id)
        return copy.deepcopy(a) if a else None

    def get_by_user_and_company_with_template(self, user_id, company_id):
        return self.get_by_user_and_company(user_id, company_id)

    def get_access_roles_for_user(self, user_id):
        return [
            {"company_id": a["company_id"], "role": a["role"], "is_active": a["is_active"]}
            for a in self.b.accesses
            if a["user_id"] == user_id
        ]

    def create(self, data):
        row = self.b._a(data["user_id"], data["company_id"], data["role"])
        row.update(data)
        self.b.accesses.append(row)
        return copy.deepcopy(row)

    def update(self, user_id, company_id, data):
        a = self.b.find(user_id, company_id)
        if not a:
            return {}
        a.update(data)
        return copy.deepcopy(a)

    def delete(self, user_id, company_id):
        a = self.b.find(user_id, company_id)
        if not a:
            return None
        self.b.accesses.remove(a)
        return a

    def count_admins(self, company_id):
        return sum(
            1
            for a in self.b.accesses
            if a["company_id"] == company_id and a["role"] == "admin"
        )


class _TplRepo:
    def __init__(self, base: _Base):
        self.b = base

    def get_company_scope(self, template_id):
        t = self.b.templates.get(template_id)
        return {"id": template_id, "company_id": t["company_id"], "is_active": True} if t else None

    def get_template_permission_ids(self, template_id):
        return list(self.b.templates[template_id]["permissions"])


class _PermRepo:
    def __init__(self, base: _Base):
        self.b = base

    def get_required_roles_by_ids(self, ids):
        return {i: self.b.permissions[i] for i in ids if i in self.b.permissions}

    def get_permission_ids(self, user_id, company_id, role_template_id=None):
        return list(self.b.user_permissions.get((user_id, company_id), set()))

    def delete_for_user_company(self, user_id, company_id):
        self.b.user_permissions.pop((user_id, company_id), None)

    def upsert(self, user_id, company_id, pid, granted_by):
        self.b.user_permissions.setdefault((user_id, company_id), set()).add(pid)


class _CompanyRepo:
    def __init__(self, base: _Base):
        self.b = base

    def get_name(self, company_id):
        return self.b.companies.get(company_id)


def _user(uid: str, base: _Base, *, platform_admin=False) -> User:
    acces = [
        CompanyAccess(
            company_id=a["company_id"],
            company_name=base.companies[a["company_id"]],
            role=a["role"],
            is_primary=a["is_primary"],
        )
        for a in base.accesses
        if a["user_id"] == uid and a["is_active"]
    ]
    return User(
        id=uid,
        email=f"{uid}@test",
        is_super_admin=platform_admin,
        accessible_companies=acces,
        active_company_id=acces[0].company_id if acces else None,
    )


@pytest.fixture
def base():
    return _Base()


@pytest.fixture
def appel(base):
    """Renvoie `faire(uid, methode, chemin, json=None, platform_admin=False)`."""
    from app.modules.access_control.api.router import router as ac_router
    from app.modules.users.api.router import router as users_router

    app = FastAPI()
    app.include_router(users_router)
    app.include_router(ac_router)
    client = TestClient(app)

    def _required_roles(ids):
        return {i: base.permissions[i] for i in ids if i in base.permissions}

    def _replace(user_id, company_id, ids, granted_by):
        base.user_permissions[(user_id, company_id)] = set(ids)

    def _user_perm_ids(user_id, company_id):
        return set(base.user_permissions.get((user_id, company_id), set()))

    def _upsert(user_id, company_id, pid, granted_by):
        base.user_permissions.setdefault((user_id, company_id), set()).add(pid)

    def _delete_for(user_id, company_id):
        base.user_permissions.pop((user_id, company_id), None)

    def _ac_access(user_id, company_id):
        return base.find(user_id, company_id)

    auth = MagicMock()
    base.auth = auth
    P = "app.modules.users.application.commands"
    patches = [
        patch(f"{P}.get_user_repository", return_value=_UserRepo(base)),
        patch(f"{P}.get_user_company_access_repository", return_value=_AccessRepo(base)),
        patch(f"{P}.get_company_repository", return_value=_CompanyRepo(base)),
        patch(f"{P}.get_default_system_template_id", return_value=None),
        patch(f"{P}.copy_template_permissions_to_user"),
        patch(f"{P}.get_role_template_repository", return_value=_TplRepo(base)),
        patch(f"{P}.get_user_permission_repository", return_value=_PermRepo(base)),
        patch(f"{P}.get_auth_provider", return_value=auth),
        patch("app.modules.users.api.router.has_any_rh_permission", return_value=False),
        patch(
            "app.modules.access_control.application.commands.permission_catalog_reader.get_user_company_access",
            side_effect=_ac_access,
        ),
        patch(
            "app.modules.access_control.application.commands.permission_catalog_reader.get_user_permission_ids",
            side_effect=_user_perm_ids,
        ),
        patch(
            "app.modules.access_control.application.commands.lire_niveaux_des_permissions",
            side_effect=_required_roles,
            create=True,
        ),
        patch(
            "app.modules.users.infrastructure.repository.user_permission_repository.delete_for_user_company",
            side_effect=_delete_for,
        ),
        patch(
            "app.modules.users.infrastructure.repository.user_permission_repository.upsert",
            side_effect=_upsert,
        ),
    ]
    for p in patches:
        p.start()

    def faire(uid, methode, chemin, json=None, platform_admin=False):
        app.dependency_overrides[get_current_user] = lambda: _user(
            uid, base, platform_admin=platform_admin
        )
        return client.request(methode, chemin, json=json)

    yield faire
    for p in patches:
        p.stop()


def _par_adresse(email, company_id, role, is_primary=False):
    return {
        "user_email": email,
        "company_id": company_id,
        "role": role,
        "is_primary": is_primary,
    }


def _par_id(user_id, company_id, role, is_primary=False):
    return {
        "user_id": user_id,
        "company_id": company_id,
        "role": role,
        "is_primary": is_primary,
    }


# ------------------------------------------------- 1. octroi : hiérarchie des rôles


class TestOctroiHierarchie:
    @pytest.mark.parametrize("role", ["admin", "rh"])
    def test_une_rh_ne_donne_ni_admin_ni_rh(self, appel, base, role):
        r = appel(RH_A, "POST", "/api/users/grant-access", _par_adresse("cible@a.fr", CO_A, role))
        assert r.status_code == 403
        assert base.find(CIBLE, CO_A)["role"] == "collaborateur"

    def test_un_collaborateur_rh_ne_donne_pas_rh(self, appel, base):
        base.accesses.append(base._a(ETRANGER, CO_A, "collaborateur"))
        r = appel(
            COLLAB_RH_A, "POST", "/api/users/grant-access",
            _par_adresse("etranger@z.fr", CO_B, "rh"),
        )
        assert r.status_code == 403

    def test_un_admin_ne_fait_pas_d_admin(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("cible@a.fr", CO_B, "admin"),
        )
        assert r.status_code == 403
        assert base.find(CIBLE, CO_B) is None


# --------------------------------------------- 2. octroi : périmètre et énumération


class TestOctroiPerimetre:
    def test_rh_ne_rattache_pas_un_compte_d_un_autre_client(self, appel, base):
        r = appel(
            RH_A, "POST", "/api/users/grant-access",
            _par_adresse("etranger@z.fr", CO_A, "collaborateur"),
        )
        assert r.status_code == 404
        assert base.find(ETRANGER, CO_A) is None

    def test_meme_reponse_compte_existant_ou_non(self, appel):
        existe = appel(
            RH_A, "POST", "/api/users/grant-access",
            _par_adresse("etranger@z.fr", CO_A, "collaborateur"),
        )
        inconnu = appel(
            RH_A, "POST", "/api/users/grant-access",
            _par_adresse("personne@nulle-part.fr", CO_A, "collaborateur"),
        )
        assert existe.status_code == inconnu.status_code == 404
        assert existe.json() == inconnu.json()
        assert "personne@nulle-part.fr" not in inconnu.text

    def test_par_identifiant_meme_perimetre(self, appel, base):
        r = appel(
            RH_A, "POST", "/api/users/grant-access-by-user-id",
            _par_id(ETRANGER, CO_A, "collaborateur"),
        )
        inconnu = appel(
            RH_A, "POST", "/api/users/grant-access-by-user-id",
            _par_id(INEXISTANT, CO_A, "collaborateur"),
        )
        assert r.status_code == inconnu.status_code == 404
        assert r.json() == inconnu.json()
        assert base.find(ETRANGER, CO_A) is None

    def test_un_super_admin_apprend_qu_une_adresse_est_inconnue(self, appel):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("personne@nulle-part.fr", CO_B, "rh"),
            platform_admin=True,
        )
        assert r.status_code == 404
        assert "Utilisateur non trouvé" in r.json()["detail"]

    def test_un_admin_ne_rattache_pas_un_autre_admin(self, appel, base):
        """Un pair (même rôle) n'est pas « géré » : pas de rattachement sans lui."""
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("admin2@groupe.fr", CO_B, "rh"),
        )
        assert r.status_code == 404
        assert base.find(ADMIN2_GROUPE, CO_B) is None


# ------------------------------------------------------- 3. octroi : soi-même


class TestOctroiSoiMeme:
    def test_par_adresse(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("admin@groupe.fr", CO_A, "rh"),
        )
        assert r.status_code == 403
        assert base.find(ADMIN_GROUPE, CO_A)["role"] == "admin"

    def test_par_identifiant(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access-by-user-id",
            _par_id(ADMIN_GROUPE, CO_A, "rh"),
        )
        assert r.status_code == 403
        assert base.find(ADMIN_GROUPE, CO_A)["role"] == "admin"


# ------------------------------------------------- 4. octroi : pas d'écrasement


class TestOctroiSansEcrasement:
    def test_acces_existant_non_reecrit(self, appel, base):
        base.accesses.append(base._a(CIBLE, CO_B, "collaborateur", lecture_seule=True))
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("cible@a.fr", CO_B, "rh"),
        )
        assert r.status_code == 400
        acces = base.find(CIBLE, CO_B)
        assert acces["role"] == "collaborateur"
        assert acces["lecture_seule"] is True

    def test_acces_coupe_jamais_reactive(self, appel, base):
        base.accesses.append(base._a(CIBLE, CO_B, "collaborateur", is_active=False))
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("cible@a.fr", CO_B, "collaborateur"),
        )
        assert r.status_code == 400
        assert "coupé" in r.json()["detail"]
        assert base.find(CIBLE, CO_B)["is_active"] is False

    def test_acces_coupe_par_identifiant(self, appel, base):
        base.accesses.append(base._a(CIBLE, CO_B, "collaborateur", is_active=False))
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access-by-user-id",
            _par_id(CIBLE, CO_B, "rh"),
        )
        assert r.status_code == 400
        assert base.find(CIBLE, CO_B)["is_active"] is False
        assert base.find(CIBLE, CO_B)["role"] == "collaborateur"

    def test_meme_un_super_admin_n_ecrase_pas(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("cible@a.fr", CO_A, "rh"),
            platform_admin=True,
        )
        assert r.status_code == 400
        assert base.find(CIBLE, CO_A)["role"] == "collaborateur"


# --------------------------------------------------------- 5. usage légitime


class TestUsageLegitime:
    def test_admin_du_groupe_ouvre_une_autre_societe_en_rh_par_adresse(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("cible@a.fr", CO_B, "rh", is_primary=True),
        )
        assert r.status_code == 200, r.text
        acces = base.find(CIBLE, CO_B)
        assert acces["role"] == "rh"
        # La société d'arrivée de la personne n'est pas le choix de celui qui ouvre.
        assert acces["is_primary"] is False

    def test_admin_du_groupe_ouvre_une_autre_societe_en_rh_par_identifiant(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access-by-user-id",
            _par_id(CIBLE, CO_B, "rh"),
        )
        assert r.status_code == 200, r.text
        assert base.find(CIBLE, CO_B)["role"] == "rh"

    def test_super_admin_rattache_qui_il_veut(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "POST", "/api/users/grant-access",
            _par_adresse("etranger@z.fr", CO_B, "admin"),
            platform_admin=True,
        )
        assert r.status_code == 200, r.text
        assert base.find(ETRANGER, CO_B)["role"] == "admin"


# ------------------------------------------- 6. modification et retrait d'accès


class TestModificationAcces:
    def test_admin_ne_promeut_pas_admin(self, appel, base):
        r = appel(ADMIN_GROUPE, "PATCH", f"/api/users/update-access/{CIBLE}/{CO_A}", {"role": "admin"})
        assert r.status_code == 403
        assert base.find(CIBLE, CO_A)["role"] == "collaborateur"

    def test_admin_ne_retrograde_pas_un_autre_admin(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "PATCH", f"/api/users/update-access/{ADMIN2_GROUPE}/{CO_A}",
            {"role": "collaborateur"},
        )
        assert r.status_code == 403
        assert base.find(ADMIN2_GROUPE, CO_A)["role"] == "admin"

    def test_personne_ne_modifie_son_propre_acces(self, appel, base):
        r = appel(
            ADMIN_GROUPE, "PATCH", f"/api/users/update-access/{ADMIN_GROUPE}/{CO_A}",
            {"is_primary": True},
        )
        assert r.status_code == 403

    def test_usage_legitime(self, appel, base):
        r = appel(ADMIN_GROUPE, "PATCH", f"/api/users/update-access/{CIBLE}/{CO_A}", {"role": "rh"})
        assert r.status_code == 200, r.text
        assert base.find(CIBLE, CO_A)["role"] == "rh"


class TestRetraitAcces:
    def test_admin_ne_retire_pas_un_autre_admin(self, appel, base):
        r = appel(ADMIN_GROUPE, "DELETE", f"/api/users/revoke-access/{ADMIN2_GROUPE}/{CO_A}")
        assert r.status_code == 403
        assert base.find(ADMIN2_GROUPE, CO_A) is not None

    def test_admin_retire_un_collaborateur(self, appel, base):
        r = appel(ADMIN_GROUPE, "DELETE", f"/api/users/revoke-access/{CIBLE}/{CO_A}")
        assert r.status_code == 200, r.text
        assert base.find(CIBLE, CO_A) is None

    def test_admin_peut_se_retirer_s_il_n_est_pas_le_dernier(self, appel, base):
        r = appel(ADMIN_GROUPE, "DELETE", f"/api/users/revoke-access/{ADMIN_GROUPE}/{CO_A}")
        assert r.status_code == 200, r.text


# ----------------------------------------------- 7. droits fins (permissions)


class TestPermissions:
    def _put(self, appel, uid, cible, ids, company=CO_A):
        return appel(
            uid, "PUT", f"/api/access-control/users/{cible}/permissions",
            {"user_id": cible, "company_id": company, "permission_ids": ids},
        )

    def test_rh_ne_se_donne_pas_de_droits(self, appel, base):
        r = self._put(appel, RH_A, RH_A, [P_RH])
        assert r.status_code == 403
        assert (RH_A, CO_A) not in base.user_permissions

    def test_rh_ne_donne_pas_un_droit_admin(self, appel, base):
        r = self._put(appel, RH_A, CIBLE, [P_COLLAB, P_BANQUE])
        assert r.status_code == 403
        assert (CIBLE, CO_A) not in base.user_permissions

    def test_rh_ne_donne_pas_un_droit_admin_en_ajout(self, appel, base):
        r = appel(
            RH_A, "POST", f"/api/access-control/users/{CIBLE}/permissions",
            {"user_id": CIBLE, "company_id": CO_A, "permission_ids": [P_BANQUE]},
        )
        assert r.status_code == 403

    def test_rh_garde_un_droit_admin_deja_donne_par_un_admin(self, appel, base):
        base.user_permissions[(CIBLE, CO_A)] = {P_BANQUE}
        r = self._put(appel, RH_A, CIBLE, [P_BANQUE, P_RH])
        assert r.status_code == 200, r.text
        assert base.user_permissions[(CIBLE, CO_A)] == {P_BANQUE, P_RH}

    def test_permission_inconnue_refusee(self, appel, base):
        r = self._put(appel, RH_A, CIBLE, [P_INCONNUE])
        assert r.status_code == 403

    def test_usage_legitime(self, appel, base):
        r = self._put(appel, RH_A, CIBLE, [P_COLLAB, P_RH, P_LIBRE])
        assert r.status_code == 200, r.text
        assert base.user_permissions[(CIBLE, CO_A)] == {P_COLLAB, P_RH, P_LIBRE}

    def test_admin_donne_un_droit_admin(self, appel, base):
        r = self._put(appel, ADMIN_GROUPE, CIBLE, [P_BANQUE])
        assert r.status_code == 200, r.text


# ------------------------------- 7 bis. droits fins à la création / modification


def _creation(company_id, role, template=None, permissions=()):
    return {
        "email": "nouveau@a.fr",
        "password": "motdepasse-long",
        "first_name": "N",
        "last_name": "N",
        "company_accesses": [
            {
                "company_id": company_id,
                "base_role": role,
                "is_primary": True,
                "role_template_id": template,
                "permission_ids": list(permissions),
            }
        ],
    }


class TestDroitsFinsCreationModification:
    def test_rh_ne_cree_pas_un_compte_avec_un_droit_admin(self, appel, base):
        r = appel(RH_A, "POST", "/api/users/create-with-permissions",
                  _creation(CO_A, "custom", TPL_COMMUN_RH, [P_BANQUE]))
        assert r.status_code == 403
        base.auth.create_user.assert_not_called()

    def test_rh_ne_cree_pas_avec_un_modele_portant_un_droit_admin(self, appel, base):
        r = appel(RH_A, "POST", "/api/users/create-with-permissions",
                  _creation(CO_A, "custom", TPL_GESTION_PAIE))
        assert r.status_code == 403
        base.auth.create_user.assert_not_called()

    def test_rh_ne_prend_pas_le_modele_d_une_autre_societe(self, appel, base):
        r = appel(RH_A, "POST", "/api/users/create-with-permissions",
                  _creation(CO_A, "custom", TPL_SOCIETE_Z))
        assert r.status_code == 403
        base.auth.create_user.assert_not_called()

    def test_rh_cree_un_compte_de_son_niveau(self, appel, base):
        base.auth.create_user.side_effect = RuntimeError("arrêt du test après le contrôle")
        r = appel(RH_A, "POST", "/api/users/create-with-permissions",
                  _creation(CO_A, "custom", TPL_COMMUN_RH, [P_COLLAB]))
        base.auth.create_user.assert_called_once()
        assert r.status_code == 400  # l'arrêt simulé, pas un refus de droits

    def test_rh_ne_donne_pas_un_droit_admin_en_modifiant(self, appel, base):
        r = appel(RH_A, "PUT", f"/api/users/{CIBLE}/update",
                  {"company_id": CO_A, "permission_ids": [P_COLLAB, P_BANQUE]})
        assert r.status_code == 403
        assert (CIBLE, CO_A) not in base.user_permissions

    def test_rh_modifie_les_droits_d_un_collaborateur(self, appel, base):
        base.user_permissions[(CIBLE, CO_A)] = {P_BANQUE}  # donné par un admin
        r = appel(RH_A, "PUT", f"/api/users/{CIBLE}/update",
                  {"company_id": CO_A, "permission_ids": [P_BANQUE, P_RH]})
        assert r.status_code == 200, r.text
        assert base.user_permissions[(CIBLE, CO_A)] == {P_BANQUE, P_RH}


class TestModeleDeRole:
    def _creer(self, appel, uid, ids):
        with patch(
            "app.modules.access_control.application.commands.role_template_repository"
        ) as repo:
            repo.role_template_name_exists.return_value = False
            repo.create_role_template.return_value = "tpl-nouveau"
            r = appel(uid, "POST", "/api/access-control/role-templates/quick-create",
                      {"name": "Modèle", "job_title": "Poste", "base_role": "custom",
                       "company_id": CO_A, "permission_ids": ids})
            return r, repo

    def test_rh_ne_cree_pas_un_modele_avec_un_droit_admin(self, appel):
        r, repo = self._creer(appel, RH_A, [P_RH, P_BANQUE])
        assert r.status_code == 403
        repo.create_role_template.assert_not_called()

    def test_rh_cree_un_modele_de_son_niveau(self, appel):
        r, repo = self._creer(appel, RH_A, [P_RH, P_LIBRE])
        assert r.status_code == 201, r.text
        repo.create_role_template.assert_called_once()


# ---------------------------------------- 8. compte en consultation (garde globale)


@pytest.mark.parametrize(
    "methode,chemin",
    [
        ("POST", "/api/users/grant-access"),
        ("POST", "/api/users/grant-access-by-user-id"),
        ("PATCH", "/api/users/update-access/u/c"),
        ("DELETE", "/api/users/revoke-access/u/c"),
        ("POST", "/api/users/create-with-permissions"),
        ("PUT", "/api/users/u/update"),
        ("PUT", "/api/access-control/users/u/permissions"),
        ("POST", "/api/access-control/users/u/permissions"),
        ("POST", "/api/access-control/role-templates/quick-create"),
    ],
)
def test_consultation_refuse_toute_gestion_d_acces(methode, chemin):
    assert permis_en_consultation(methode, chemin, {}) is False
