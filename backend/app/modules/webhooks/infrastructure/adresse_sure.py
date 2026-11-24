"""Garde des adresses de webhook : https et hôte public seulement (24/11/2026).

Le serveur fait lui-même le POST vers l'adresse saisie par un compte RH. Sans garde,
cette adresse peut viser le serveur (localhost), le réseau interne ou les métadonnées
du cloud (169.254.169.254) : SSRF. La règle :

- seul `https://` est accepté ;
- le nom est résolu et TOUTES ses adresses doivent être publiques (`is_global`), ni
  multicast, ni réservées ; une adresse IPv4 portée dans IPv6 (::ffff:, NAT64, 6to4,
  Teredo) est jugée sur l'IPv4 qu'elle porte ;
- un nom introuvable est refusé.

La garde vaut à l'enregistrement ET à chaque envoi : à l'envoi, la connexion part sur
l'adresse vérifiée (voir `repository._post_webhook`), pour qu'un DNS qui change de
réponse entre la vérification et la connexion ne contourne pas la règle.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

IP = ipaddress.IPv4Address | ipaddress.IPv6Address

_NAT64 = ipaddress.ip_network("64:ff9b::/96")


class AdresseWebhookRefusee(ValueError):
    """Adresse de webhook refusée ; le message est affiché tel quel à l'écran."""


@dataclass(frozen=True)
class AdresseVerifiee:
    url: str
    hote: str
    port: int | None
    adresses: tuple[IP, ...]


def _resoudre(hote: str, port: int) -> list[str]:
    """Adresses de `hote` (sans doublon, ordre gardé). Lève OSError si introuvable."""
    vues: list[str] = []
    for *_rest, sockaddr in socket.getaddrinfo(hote, port, type=socket.SOCK_STREAM):
        adresse = str(sockaddr[0]).split("%", 1)[0]  # fe80::1%en0 -> fe80::1
        if adresse not in vues:
            vues.append(adresse)
    return vues


def _ipv4_portee(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]
    return None


def adresse_publique(ip: IP) -> bool:
    """True si l'adresse est joignable sur Internet et ne vise rien d'interne."""
    if isinstance(ip, ipaddress.IPv6Address):
        portee = _ipv4_portee(ip)
        if portee is not None and not adresse_publique(portee):
            return False
    return bool(ip.is_global) and not (
        getattr(ip, "is_site_local", False)  # fec0::/10, obsolète mais routable en interne
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
    )


def verifier_adresse_webhook(url: str) -> AdresseVerifiee:
    """Vérifie `url` (schéma, hôte, résolution) ; lève AdresseWebhookRefusee sinon."""
    texte = str(url or "").strip()
    try:
        parties = urlsplit(texte)
        port = parties.port
    except ValueError:
        raise AdresseWebhookRefusee("Adresse du webhook invalide.") from None
    if parties.scheme.lower() != "https":
        raise AdresseWebhookRefusee(
            "L'adresse du webhook doit commencer par https:// (les adresses http:// ne sont pas acceptées)."
        )
    hote = (parties.hostname or "").strip()
    if not hote:
        raise AdresseWebhookRefusee("Adresse du webhook invalide : le nom du serveur manque.")
    try:
        brutes = _resoudre(hote, port or 443)
    except (OSError, UnicodeError):
        raise AdresseWebhookRefusee(
            f"Le serveur « {hote} » est introuvable : vérifiez l'adresse du webhook."
        ) from None
    if not brutes:
        raise AdresseWebhookRefusee(
            f"Le serveur « {hote} » est introuvable : vérifiez l'adresse du webhook."
        )
    adresses: list[IP] = []
    for brute in brutes:
        try:
            ip = ipaddress.ip_address(brute)
        except ValueError:
            raise AdresseWebhookRefusee(
                f"Le serveur « {hote} » répond par une adresse illisible : webhook refusé."
            ) from None
        if not adresse_publique(ip):
            raise AdresseWebhookRefusee(
                f"Le serveur « {hote} » pointe vers une adresse interne ou réservée "
                "(réseau privé, localhost, métadonnées du cloud…) : un webhook ne peut viser "
                "qu'un serveur public sur Internet."
            )
        adresses.append(ip)
    return AdresseVerifiee(url=texte, hote=hote, port=port, adresses=tuple(adresses))
