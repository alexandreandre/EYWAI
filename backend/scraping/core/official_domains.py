"""
Domaines officiels français — source unique (validation URL, Sonar, citations IA).

Deux listes :
- OFFICIAL_URL_SUFFIXES : acceptation d'une URL (hostname == suffix ou *.suffix)
- OFFICIAL_WEB_SEARCH_DOMAINS : ciblage Sonar / Perplexity (include_domains)
"""

from __future__ import annotations

from urllib.parse import urlparse

# Hostnames refusés même si le suffixe matche (sources complémentaires, pas officielles).
_EXCLUDED_HOST_SUFFIXES = ("legisocial.fr",)

# Suffixes d'hôtes reconnus comme sources État / opérateurs de protection sociale.
OFFICIAL_URL_SUFFIXES: tuple[str, ...] = (
    "gouv.fr",  # entreprendre.service-public.gouv.fr, travail-emploi.gouv.fr, etc.
    "urssaf.fr",
    "ameli.fr",
    "agirc-arrco.fr",
    "securite-sociale.fr",
    "service-public.fr",
    "impots.gouv.fr",
    "unedic.org",
    "francetravail.fr",
    "net-entreprises.fr",
    "cnav.fr",
    "lassuranceretraite.fr",
    "assurance-retraite.fr",
)

# Domaines explicites pour la recherche web Sonar (include_domains).
OFFICIAL_WEB_SEARCH_DOMAINS: tuple[str, ...] = (
    "gouv.fr",
    "urssaf.fr",
    "boss.gouv.fr",
    "service-public.fr",
    "service-public.gouv.fr",
    "entreprendre.service-public.gouv.fr",
    "particuliers.service-public.gouv.fr",
    "bofip.impots.gouv.fr",
    "impots.gouv.fr",
    "legifrance.gouv.fr",
    "travail-emploi.gouv.fr",
    "travail.gouv.fr",
    "emploi.gouv.fr",
    "agirc-arrco.fr",
    "securite-sociale.fr",
    "ameli.fr",
    "unedic.org",
    "francetravail.fr",
    "net-entreprises.fr",
)


def hostname_from_url(url: str) -> str:
    try:
        return (urlparse(url.strip()).hostname or "").lower()
    except Exception:
        return ""


def host_is_official(url: str) -> bool:
    """True si l'URL pointe vers un domaine officiel (hors LegiSocial)."""
    host = hostname_from_url(url)
    if not host:
        return False
    for excluded in _EXCLUDED_HOST_SUFFIXES:
        if host == excluded or host.endswith(f".{excluded}"):
            return False
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in OFFICIAL_URL_SUFFIXES)


def official_domains_prompt_hint() -> str:
    """Résumé court pour les prompts IA."""
    return (
        "Domaines autorisés : tout *.gouv.fr (Service-Public, Entreprendre, ministères), "
        "urssaf.fr, boss.gouv.fr, legifrance.gouv.fr, impots.gouv.fr / BOFiP, "
        "agirc-arrco.fr, securite-sociale.fr, ameli.fr, unedic.org, francetravail.fr, "
        "net-entreprises.fr. Pas LegiSocial si une source État existe."
    )
