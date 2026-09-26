"""Le filet avant/après : jamais d'écriture, rejeu fidèle, comparaison au centime."""

import httpx
import pytest

from scripts.filet_paie import (
    EcritureInterdite,
    Interception,
    RequeteInconnue,
    _aplatir,
    comparer,
)

BASE = "https://exemple.supabase.co"


def _client_avec_compteur():
    appels = []

    def repondre(request: httpx.Request) -> httpx.Response:
        appels.append(request)
        return httpx.Response(200, json=[{"id": 1, "valeur": 12.5}])

    return httpx.Client(transport=httpx.MockTransport(repondre)), appels


def test_une_ecriture_est_refusee_avant_de_partir():
    client, appels = _client_avec_compteur()
    with Interception("photo"):
        with pytest.raises(EcritureInterdite):
            client.post(f"{BASE}/rest/v1/payslips", json={"net": 1})
        with pytest.raises(EcritureInterdite):
            client.patch(f"{BASE}/rest/v1/employees?id=eq.1", json={"x": 1})
        with pytest.raises(EcritureInterdite):
            client.post(f"{BASE}/storage/v1/object/payslips/a.pdf", content=b"%PDF")
    assert appels == []


def test_la_photo_enregistre_et_le_rejeu_repond_sans_reseau():
    client, appels = _client_avec_compteur()
    with Interception("photo") as photo:
        r1 = client.get(f"{BASE}/rest/v1/employees?select=id")
        r2 = client.post(f"{BASE}/rest/v1/rpc/lire_un_truc", json={"a": 1})
    assert len(appels) == 2 and r1.json() == r2.json()

    client_sans_reseau = httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail("réseau appelé")))
    with Interception("rejeu", photo.cassette):
        assert client_sans_reseau.get(f"{BASE}/rest/v1/employees?select=id").json() == [{"id": 1, "valeur": 12.5}]
        assert client_sans_reseau.post(f"{BASE}/rest/v1/rpc/lire_un_truc", json={"a": 1}).status_code == 200
        with pytest.raises(RequeteInconnue):
            client_sans_reseau.get(f"{BASE}/rest/v1/employees?select=nom")


def test_l_interception_est_retiree_a_la_sortie():
    original = httpx.Client.send
    with Interception("photo"):
        assert httpx.Client.send is not original
    assert httpx.Client.send is original


def test_les_lignes_sont_indexees_par_libelle():
    plat = _aplatir({"lignes": [{"libelle": "Salaire de base", "montant": 100}, {"libelle": "Prime", "montant": 5}]})
    assert plat == {"lignes[Salaire de base].montant": 100, "lignes[Prime].montant": 5}


def test_une_ligne_ajoutee_ne_decale_pas_les_autres():
    avant = {"b": {"payslip_data": {"lignes": [{"libelle": "A", "m": 1.0}, {"libelle": "B", "m": 2.0}]}}}
    apres = {"b": {"payslip_data": {"lignes": [{"libelle": "Nouvelle", "m": 9.0}, {"libelle": "A", "m": 1.0}, {"libelle": "B", "m": 2.0}]}}}
    ecarts = comparer(avant, apres)
    assert ecarts == {"b": [("payslip_data.lignes[Nouvelle].m", "—", 9.0)]}


def test_la_comparaison_tolere_moins_d_un_demi_centime():
    avant = {"b": {"net": 1500.004}}
    assert comparer(avant, {"b": {"net": 1500.0}}) == {}
    assert comparer(avant, {"b": {"net": 1500.01}}) != {}


def test_les_champs_volatils_sont_ignores():
    assert comparer({"b": {"date_generation": "hier", "net": 1}}, {"b": {"date_generation": "aujourd'hui", "net": 1}}) == {}
