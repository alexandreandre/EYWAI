"""Un webhook ne vise qu'une adresse https publique (24/11/2026).

Un compte RH enregistre l'adresse ; « Tester » et chaque événement font un vrai POST depuis
le serveur. Sans garde, l'adresse peut viser le serveur lui-même (localhost), le réseau
interne ou les métadonnées du cloud (169.254.169.254) : SSRF. La garde refuse à
l'enregistrement ET à l'envoi ; à l'envoi, le nom est résolu, toutes ses adresses sont
vérifiées et la connexion part sur l'adresse vérifiée (pas de seconde résolution), sans
suivre de redirection. Aucun accès réseau ici : la résolution et httpx sont doublés.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.webhooks.infrastructure import adresse_sure
from app.modules.webhooks.infrastructure.adresse_sure import (
    AdresseWebhookRefusee,
    verifier_adresse_webhook,
)
from app.modules.webhooks.infrastructure.repository import WebhookRepository

pytestmark = pytest.mark.unit

PUBLIQUE = "93.184.215.14"


@pytest.fixture
def dns(monkeypatch):
    """Table de résolution doublée : nom -> adresses ; nom absent = introuvable."""
    table: dict[str, list[str]] = {}

    def resoudre(hote, port):
        if hote in table:
            return list(table[hote])
        raise OSError("nom introuvable")

    monkeypatch.setattr(adresse_sure, "_resoudre", resoudre)
    return table


# --- la règle ---------------------------------------------------------------------------------


def test_une_adresse_https_publique_est_acceptee(dns):
    dns["hooks.exemple.fr"] = [PUBLIQUE]
    ok = verifier_adresse_webhook("https://hooks.exemple.fr/martine?x=1")
    assert ok.hote == "hooks.exemple.fr"
    assert [str(a) for a in ok.adresses] == [PUBLIQUE]


@pytest.mark.parametrize("url", ["http://hooks.exemple.fr/x", "ftp://hooks.exemple.fr/x", "hooks.exemple.fr"])
def test_seul_https_est_accepte(dns, url):
    dns["hooks.exemple.fr"] = [PUBLIQUE]
    with pytest.raises(AdresseWebhookRefusee, match="https://"):
        verifier_adresse_webhook(url)


def test_une_adresse_sans_hote_est_refusee(dns):
    with pytest.raises(AdresseWebhookRefusee):
        verifier_adresse_webhook("https:///chemin")


def test_un_hote_introuvable_est_refuse(dns):
    with pytest.raises(AdresseWebhookRefusee, match="introuvable"):
        verifier_adresse_webhook("https://nulle-part.exemple.fr/x")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",          # bouclage
        "10.1.2.3",           # privée
        "172.16.0.5",         # privée
        "192.168.1.1",        # privée
        "100.64.0.1",         # partagée (CGNAT)
        "169.254.169.254",    # lien-local : métadonnées du cloud
        "0.0.0.0",            # non spécifiée
        "224.0.0.1",          # multicast
        "240.0.0.1",          # réservée
        "255.255.255.255",    # diffusion
        "::1",                # bouclage IPv6
        "fe80::1",            # lien-local IPv6
        "fc00::1",            # unique locale IPv6
        "ff02::1",            # multicast IPv6
        "::ffff:127.0.0.1",   # IPv4 dans IPv6
        "::ffff:169.254.169.254",
        "64:ff9b::a9fe:a9fe",  # NAT64 vers 169.254.169.254
        "2002:a9fe:a9fe::1",   # 6to4 vers 169.254.169.254
    ],
)
def test_une_adresse_interne_est_refusee(dns, ip):
    dns["piege.exemple.fr"] = [ip]
    with pytest.raises(AdresseWebhookRefusee, match="interne"):
        verifier_adresse_webhook("https://piege.exemple.fr/x")


def test_une_seule_adresse_interne_parmi_plusieurs_suffit_a_refuser(dns):
    dns["mixte.exemple.fr"] = [PUBLIQUE, "10.0.0.7"]
    with pytest.raises(AdresseWebhookRefusee):
        verifier_adresse_webhook("https://mixte.exemple.fr/x")


def test_localhost_et_ip_litterale_sont_refuses(dns):
    dns["localhost"] = ["127.0.0.1"]
    dns["169.254.169.254"] = ["169.254.169.254"]
    for url in ("https://localhost/x", "https://169.254.169.254/latest/meta-data"):
        with pytest.raises(AdresseWebhookRefusee):
            verifier_adresse_webhook(url)


def test_la_resolution_reelle_est_branchee_sur_getaddrinfo(monkeypatch):
    appels = []

    def faux_getaddrinfo(hote, port, *a, **k):
        appels.append((hote, port))
        return [(2, 1, 6, "", ("10.0.0.1", port)), (10, 1, 6, "", ("fe80::1%en0", port, 0, 1))]

    monkeypatch.setattr(adresse_sure.socket, "getaddrinfo", faux_getaddrinfo)
    assert adresse_sure._resoudre("x.exemple.fr", 443) == ["10.0.0.1", "fe80::1"]
    assert appels == [("x.exemple.fr", 443)]


# --- l'envoi ----------------------------------------------------------------------------------


def _client_double(status=200, text="ok"):
    client = MagicMock()
    client.__enter__.return_value.post.return_value = MagicMock(status_code=status, text=text)
    return client


def test_a_l_envoi_une_adresse_interne_ne_part_pas(dns):
    dns["piege.exemple.fr"] = ["169.254.169.254"]
    with patch("app.modules.webhooks.infrastructure.repository.httpx.Client") as fabrique:
        status, texte, _, _ = WebhookRepository()._post_webhook(
            {"url": "https://piege.exemple.fr/x"}, "x.test", "c", {}
        )
    fabrique.assert_not_called()
    assert status == 0
    assert "interne" in texte


def test_a_l_envoi_la_connexion_part_sur_l_adresse_verifiee_sans_redirection(dns):
    dns["hooks.exemple.fr"] = [PUBLIQUE]
    client = _client_double()
    with patch("app.modules.webhooks.infrastructure.repository.httpx.Client", return_value=client) as fabrique:
        status, _, _, _ = WebhookRepository()._post_webhook(
            {"url": "https://hooks.exemple.fr:8443/martine?x=1"}, "x.test", "c", {"a": 1}
        )
    assert status == 200
    options = fabrique.call_args.kwargs
    assert options["follow_redirects"] is False
    assert options["trust_env"] is False
    appel = client.__enter__.return_value.post.call_args
    assert appel.args[0] == f"https://{PUBLIQUE}:8443/martine?x=1"
    assert appel.kwargs["headers"]["Host"] == "hooks.exemple.fr:8443"
    assert appel.kwargs["extensions"] == {"sni_hostname": "hooks.exemple.fr"}


def test_a_l_envoi_une_ipv6_publique_est_entre_crochets(dns):
    dns["v6.exemple.fr"] = ["2606:4700::1111"]
    client = _client_double()
    with patch("app.modules.webhooks.infrastructure.repository.httpx.Client", return_value=client):
        WebhookRepository()._post_webhook({"url": "https://v6.exemple.fr/h"}, "x.test", "c", {})
    appel = client.__enter__.return_value.post.call_args
    assert appel.args[0] == "https://[2606:4700::1111]/h"
    assert appel.kwargs["headers"]["Host"] == "v6.exemple.fr"


def test_un_evenement_vers_une_adresse_interne_est_journalise_sans_post(dns):
    dns["piege.exemple.fr"] = ["10.0.0.1"]
    repo = WebhookRepository()
    lignes = MagicMock()
    lignes.data = [{"id": "w1", "url": "https://piege.exemple.fr/x", "events": ["x.test"], "is_active": True}]
    with patch("app.modules.webhooks.infrastructure.repository.supabase") as sb, patch(
        "app.modules.webhooks.infrastructure.repository.httpx.Client"
    ) as fabrique, patch.object(repo, "_persist_delivery") as journal:
        sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = lignes
        repo.trigger_event("c", "x.test", {})
    fabrique.assert_not_called()
    journal.assert_called_once()
    assert journal.call_args.args[3] == 0
    assert "interne" in journal.call_args.args[4]


# --- l'enregistrement et le test ---------------------------------------------------------------


def test_la_creation_refuse_une_adresse_interne_avant_toute_ecriture(dns):
    from app.modules.webhooks.application import service

    dns["piege.exemple.fr"] = ["127.0.0.1"]
    with patch.object(service.webhook_repository, "create") as creer:
        with pytest.raises(AdresseWebhookRefusee):
            service.create_webhook("c", {"name": "n", "url": "https://piege.exemple.fr/", "events": ["x"]}, "u")
    creer.assert_not_called()


def test_la_modification_refuse_une_adresse_interne_et_laisse_passer_le_reste(dns):
    from app.modules.webhooks.application import service

    dns["piege.exemple.fr"] = ["192.168.0.1"]
    with patch.object(service.webhook_repository, "update", return_value={"id": "w"}) as maj:
        with pytest.raises(AdresseWebhookRefusee):
            service.update_webhook("w", "c", {"url": "https://piege.exemple.fr/"})
        maj.assert_not_called()
        service.update_webhook("w", "c", {"name": "Renommé"})
    maj.assert_called_once()


def test_tester_un_webhook_enregistre_vers_une_adresse_interne_est_refuse(dns):
    dns["piege.exemple.fr"] = ["127.0.0.1"]
    repo = WebhookRepository()
    with patch.object(repo, "get_by_id", return_value={"id": "w", "url": "https://piege.exemple.fr/"}), patch(
        "app.modules.webhooks.infrastructure.repository.httpx.Client"
    ) as fabrique:
        with pytest.raises(AdresseWebhookRefusee):
            repo.send_test("w", "c")
    fabrique.assert_not_called()


def _utilisateur():
    u = MagicMock()
    u.id = "u1"
    return u


def test_l_ecran_recoit_un_message_clair_en_francais(dns):
    from app.modules.webhooks.api import router
    from app.modules.webhooks.schemas.responses import WebhookCreate

    corps = WebhookCreate(name="n", url="http://hooks.exemple.fr/x", events=["employee.hired"])
    with patch.object(router, "require_rh_access"):
        with pytest.raises(HTTPException) as erreur:
            router.create_webhook(corps, current_user=_utilisateur(), company_id="c")
    assert erreur.value.status_code == 400
    assert "https://" in erreur.value.detail


def test_le_bouton_tester_recoit_un_message_clair(dns):
    from app.modules.webhooks.api import router

    with patch.object(router.webhook_service, "send_test_webhook", side_effect=AdresseWebhookRefusee("Adresse interne refusée.")), patch.object(
        router, "require_rh_access"
    ):
        with pytest.raises(HTTPException) as erreur:
            router.test_webhook("w", current_user=_utilisateur(), company_id="c")
    assert erreur.value.status_code == 400
    assert erreur.value.detail == "Adresse interne refusée."
