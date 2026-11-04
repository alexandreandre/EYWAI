"""Barèmes gardés par processus : relus seulement quand une ligne active a changé.

Audit de modernisation du 03/11/2026 (R2, geste 4a) : chaque génération relisait
les 4 Mo des barèmes actifs. Le processus les garde, et compare à chaque
chargement l'empreinte (id, xmin) des lignes actives : Postgres donne un nouveau
`xmin` à toute ligne écrite, même par une migration qui ne change pas `version`.
Ces tests jouent une base PostgREST en mémoire : toute écriture vide le cache,
et chaque appel rend une copie neuve.
"""

from __future__ import annotations

import copy
import itertools

import pytest
from postgrest.exceptions import APIError

from app.modules.payroll.engine import baremes_loader
from app.modules.payroll.engine.baremes_loader import charger_db_baremes

pytestmark = pytest.mark.unit

TAUX_VM = [{"commune": f"C{i}", "taux": 0.02} for i in range(3)]


class _Base:
    """`payroll_config` vue par PostgREST : chaque écriture pose un nouveau xmin."""

    def __init__(self, *, rend_xmin: bool = True) -> None:
        self.xid = itertools.count(1000)
        self.lignes: list[dict] = []
        self.rend_xmin = rend_xmin
        self.lectures: list[str] = []
        self.panne_empreinte = False
        self.ajouter("smic", {"horaire": 12.02})
        self.ajouter("taux_vmrr", TAUX_VM)

    def ajouter(self, cle: str, donnees, version: int = 1) -> dict:
        ligne = {
            "id": len(self.lignes) + 1,
            "xmin": str(next(self.xid)),
            "config_key": cle,
            "config_data": donnees,
            "version": version,
            "is_active": True,
        }
        self.lignes.append(ligne)
        return ligne

    def modifier(self, cle: str, **champs) -> None:
        """UPDATE en place, comme une migration : `version` ne bouge pas."""
        for ligne in self.lignes:
            if ligne["config_key"] == cle and ligne["is_active"]:
                ligne.update(champs, xmin=str(next(self.xid)))

    def select(self, colonnes: str) -> list[dict]:
        noms = [c.strip() for c in colonnes.split(",")]
        self.lectures.append("config_data" if "config_data" in noms else "empreinte")
        if "xmin" in noms and not self.rend_xmin:
            raise APIError({"code": "42703", "message": "column payroll_config.xmin does not exist"})
        if noms == ["id", "xmin"] and self.panne_empreinte:
            raise ConnectionError("coupure")
        # Du JSON sur le réseau : chaque réponse est neuve.
        return copy.deepcopy(
            [{n: ligne[n] for n in noms} for ligne in self.lignes if ligne["is_active"]]
        )


class _Requete:
    def __init__(self, base: _Base) -> None:
        self.base = base
        self.colonnes = ""

    def select(self, colonnes: str):
        self.colonnes = colonnes
        return self

    def eq(self, colonne: str, valeur):
        assert (colonne, valeur) == ("is_active", True)
        return self

    def execute(self):
        return type("Reponse", (), {"data": self.base.select(self.colonnes)})()


class _Client:
    def __init__(self, base: _Base, url: str = "https://base.test") -> None:
        self.base = base
        self.supabase_url, self.supabase_key = url, "cle"

    def table(self, nom: str):
        assert nom == "payroll_config"
        return _Requete(self.base)


@pytest.fixture(autouse=True)
def _cache_vide():
    vider = getattr(baremes_loader, "vider_baremes_gardes", lambda: None)
    vider()
    yield
    vider()


def test_sans_changement_les_4_mo_ne_sont_pas_relus():
    base = _Base()
    client = _Client(base)

    premier = charger_db_baremes(client)
    second = charger_db_baremes(client)
    troisieme = charger_db_baremes(client)

    assert premier == second == troisieme == {"smic": {"horaire": 12.02}, "taux_vmrr": TAUX_VM}
    assert base.lectures == ["config_data", "empreinte", "empreinte"]


def test_chaque_appel_rend_une_copie_neuve():
    """Le moteur modifie ses barèmes (avantages en nature, surcharges) : le
    calcul suivant ne doit jamais en hériter."""
    client = _Client(_Base())
    premier = charger_db_baremes(client)
    premier["smic"]["horaire"] = 99.0
    premier["taux_vmrr"].append({"commune": "X", "taux": 1})

    second = charger_db_baremes(client)
    assert second["smic"] == {"horaire": 12.02}
    assert second["taux_vmrr"] == TAUX_VM
    assert charger_db_baremes(client) is not second


def test_une_ligne_modifiee_en_place_vide_le_cache():
    """Une migration fait UPDATE payroll_config SET config_data = … sans toucher
    `version` : seul le xmin change, et il suffit."""
    base = _Base()
    client = _Client(base)
    assert charger_db_baremes(client)["smic"] == {"horaire": 12.02}

    base.modifier("smic", config_data={"horaire": 12.31})

    assert charger_db_baremes(client)["smic"] == {"horaire": 12.31}
    assert base.lectures[-2:] == ["empreinte", "config_data"]
    # Puis de nouveau gardé.
    assert charger_db_baremes(client)["smic"] == {"horaire": 12.31}
    assert base.lectures[-1] == "empreinte"


def test_une_nouvelle_version_vide_le_cache():
    """Le versionnage des taux (scraping, saisie manuelle) : la ligne active est
    désactivée, une nouvelle prend sa place."""
    base = _Base()
    client = _Client(base)
    charger_db_baremes(client)

    base.modifier("smic", is_active=False)
    base.ajouter("smic", {"horaire": 12.50}, version=2)

    assert charger_db_baremes(client)["smic"] == {"horaire": 12.50}


def test_une_ligne_desactivee_disparait():
    base = _Base()
    client = _Client(base)
    charger_db_baremes(client)

    base.modifier("taux_vmrr", is_active=False)

    assert charger_db_baremes(client) == {"smic": {"horaire": 12.02}}


def test_une_ligne_ajoutee_apparait():
    base = _Base()
    client = _Client(base)
    charger_db_baremes(client)

    base.ajouter("pss", {"mensuel": 4005})

    assert charger_db_baremes(client)["pss"] == {"mensuel": 4005}


def test_empreinte_illisible_les_baremes_sont_relus():
    base = _Base()
    client = _Client(base)
    charger_db_baremes(client)
    base.panne_empreinte = True
    base.modifier("smic", config_data={"horaire": 12.31})

    assert charger_db_baremes(client)["smic"] == {"horaire": 12.31}


def test_base_sans_xmin_tout_est_relu_comme_avant():
    base = _Base(rend_xmin=False)
    client = _Client(base)

    assert charger_db_baremes(client)["smic"] == {"horaire": 12.02}
    base.modifier("smic", config_data={"horaire": 12.31})
    assert charger_db_baremes(client)["smic"] == {"horaire": 12.31}
    # Une seule tentative avec xmin, puis la lecture d'avant à chaque appel.
    nb = len(base.lectures)
    charger_db_baremes(client)
    assert len(base.lectures) == nb + 1


def test_deux_bases_ne_partagent_rien():
    base_a, base_b = _Base(), _Base()
    base_b.modifier("smic", config_data={"horaire": 11.88})
    client_a, client_b = _Client(base_a, "https://a.test"), _Client(base_b, "https://b.test")

    assert charger_db_baremes(client_a)["smic"] == {"horaire": 12.02}
    assert charger_db_baremes(client_b)["smic"] == {"horaire": 11.88}
    assert charger_db_baremes(client_a)["smic"] == {"horaire": 12.02}


def test_aucune_ligne_active_reste_une_erreur():
    base = _Base()
    for cle in ("smic", "taux_vmrr"):
        base.modifier(cle, is_active=False)
    with pytest.raises(RuntimeError, match="Aucune configuration de paie active"):
        charger_db_baremes(_Client(base))
