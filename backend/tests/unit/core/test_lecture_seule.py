"""Lecture seule : un calcul répété lit la base une fois et n'y écrit jamais. [lot 31]

Le brut d'une prime pour un net voulu (lot 30) rejoue le bulletin du mois
trois à cinq fois ; chaque essai relisait toute la base, 56 requêtes environ :
16,7 s sur le site de test pour une prime de 100 € nets. Dans
`lecture_seule()`, le client HTTP de Supabase garde chaque lecture et rend la
même réponse aux essais suivants ; une écriture est refusée avant de partir.
Hors du bloc, rien ne change.
"""

from __future__ import annotations

import gzip
import json

import httpx
import pytest

from app.core.lecture_seule import (
    ClientHttpSupabase,
    EcritureEnLectureSeule,
    ecritures_permises,
    lecture_seule,
)

pytestmark = pytest.mark.unit

URL = "https://base.test/rest/v1/employees?select=%2A&id=eq.emp"


class _Base:
    """Un serveur qui compte ce qu'il reçoit."""

    def __init__(self, statut: int = 200, *, compresse: bool = False):
        self.recues: list[tuple[str, str]] = []
        self.statut = statut
        self.compresse = compresse

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.recues.append((request.method, str(request.url)))
        corps = json.dumps([{"id": "emp", "lecture": len(self.recues)}]).encode()
        if self.compresse:
            return httpx.Response(
                self.statut, content=gzip.compress(corps), headers={"content-encoding": "gzip"}
            )
        return httpx.Response(self.statut, content=corps)


def _client(base: _Base) -> ClientHttpSupabase:
    return ClientHttpSupabase(transport=httpx.MockTransport(base))


def test_hors_lecture_seule_chaque_lecture_part():
    base = _Base()
    client = _client(base)

    client.get(URL)
    client.get(URL)

    assert len(base.recues) == 2


def test_en_lecture_seule_une_meme_lecture_ne_part_qu_une_fois():
    base = _Base()
    client = _client(base)

    with lecture_seule():
        premiere = client.get(URL)
        seconde = client.get(URL)

    assert len(base.recues) == 1
    assert premiere.json() == seconde.json() == [{"id": "emp", "lecture": 1}]
    assert seconde.status_code == 200


def test_une_reponse_compressee_se_relit_depuis_la_memoire():
    base = _Base(compresse=True)
    client = _client(base)

    with lecture_seule():
        client.get(URL)
        seconde = client.get(URL)

    assert len(base.recues) == 1
    assert seconde.json() == [{"id": "emp", "lecture": 1}]


def test_deux_lectures_differentes_partent_toutes_les_deux():
    base = _Base()
    client = _client(base)

    with lecture_seule():
        client.get(URL)
        client.get(URL.replace("eq.emp", "eq.autre"))
        # Même adresse, autre forme de réponse (un objet au lieu d'une liste).
        client.get(URL, headers={"Accept": "application/vnd.pgrst.object+json"})

    assert len(base.recues) == 3


def test_le_cookie_de_cloudflare_ne_distingue_pas_deux_lectures():
    # Supabase répond derrière Cloudflare, qui pose un cookie `__cf_bm` ; le
    # client le renvoie ensuite. Il ne change rien aux données lues.
    base = _Base()
    client = _client(base)

    with lecture_seule():
        client.get(URL)
        client.get(URL, headers={"Cookie": "__cf_bm=autre-valeur"})

    assert len(base.recues) == 1


def test_la_memoire_ne_survit_pas_au_bloc():
    base = _Base()
    client = _client(base)

    with lecture_seule():
        client.get(URL)
    with lecture_seule():
        client.get(URL)

    assert len(base.recues) == 2


def test_une_erreur_du_serveur_n_est_pas_gardee():
    # Une erreur passagère se relit : la reprise des requêtes doit pouvoir
    # retenter, pas retrouver l'erreur en mémoire.
    base = _Base(statut=503)
    client = _client(base)

    with lecture_seule():
        client.get(URL)
        client.get(URL)

    assert len(base.recues) == 2


@pytest.mark.parametrize("methode", ["POST", "PATCH", "PUT", "DELETE"])
def test_en_lecture_seule_une_ecriture_est_refusee_sans_partir(methode):
    base = _Base()
    client = _client(base)

    with lecture_seule(), pytest.raises(EcritureEnLectureSeule, match="lecture seule"):
        client.request(methode, URL, json={"days_granted": 2})

    assert base.recues == []


def test_hors_lecture_seule_les_ecritures_partent():
    base = _Base()
    client = _client(base)

    client.request("PATCH", URL, json={"days_granted": 2})

    assert base.recues == [("PATCH", URL)]


def test_ecritures_permises_hors_du_bloc_seulement():
    assert ecritures_permises() is True
    with lecture_seule():
        assert ecritures_permises() is False
    assert ecritures_permises() is True


def test_le_client_de_l_application_est_celui_de_la_lecture_seule():
    # Les lectures du générateur passent toutes par ce client partagé :
    # postgrest (tables) et storage.
    from app.core.database import supabase

    assert isinstance(supabase.postgrest.session, ClientHttpSupabase)
    assert isinstance(supabase.storage._client, ClientHttpSupabase)


def test_une_lecture_longue_a_decoder_se_lit_une_fois_et_se_rend_en_copie():
    # Les barèmes (`payroll_config`, 4 Mo) : les redécoder coûtait 0,2 s par essai.
    from app.core.lecture_seule import lire_une_fois

    lectures: list[int] = []

    def lire() -> dict:
        lectures.append(1)
        return {"smic": {"horaire": 12.02, "annees": [2025, 2026]}, "pas": [{"taux": 1.6}]}

    with lecture_seule():
        premiere = lire_une_fois(("payroll_config",), lire)
        premiere["smic"]["horaire"] = 0.0  # un essai qui modifierait ses barèmes
        seconde = lire_une_fois(("payroll_config",), lire)

    assert len(lectures) == 1
    assert seconde == {"smic": {"horaire": 12.02, "annees": [2025, 2026]}, "pas": [{"taux": 1.6}]}


def test_hors_lecture_seule_une_lecture_longue_se_relit_a_chaque_fois():
    from app.core.lecture_seule import lire_une_fois

    lectures: list[int] = []

    def lire() -> dict:
        lectures.append(1)
        return {"smic": {"horaire": 12.02}}

    lire_une_fois(("payroll_config",), lire)
    lire_une_fois(("payroll_config",), lire)

    assert len(lectures) == 2


def test_les_baremes_du_moteur_se_lisent_une_fois_par_calcul_en_lecture_seule():
    from app.modules.payroll.engine.baremes_loader import charger_db_baremes

    class _Requete:
        def __init__(self, journal):
            self.journal = journal

        def select(self, *_a):
            return self

        def eq(self, *_a):
            return self

        def execute(self):
            self.journal.append(1)
            return type("R", (), {"data": [{"config_key": "smic", "config_data": {"horaire": 12.02}}]})()

    class _Client:
        supabase_url, supabase_key = "https://base.test", "cle"

        def __init__(self):
            self.journal: list[int] = []

        def table(self, _nom):
            return _Requete(self.journal)

    client = _Client()
    with lecture_seule():
        assert charger_db_baremes(client) == {"smic": {"horaire": 12.02}}
        assert charger_db_baremes(client) == {"smic": {"horaire": 12.02}}
    charger_db_baremes(client)

    assert len(client.journal) == 2
