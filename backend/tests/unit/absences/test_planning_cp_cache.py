"""Le calcul des soldes lit le planning une fois par salarié, pas quatre.

Un aperçu de campagne boucle sur les salariés, et chaque salarié déclenche
plusieurs calculs de solde. Sans mutualisation, la lecture du planning et des
dates de reprise est refaite à chaque fois : mesuré à 51 s pour une société de
79 salariés.
"""

from __future__ import annotations

from app.modules.absences.infrastructure.short_cache import ShortLivedCache


def test_deux_appels_rapproches_ne_lisent_quune_fois():
    appels = []
    cache = ShortLivedCache(ttl_seconds=60, clock=lambda: 1000.0)

    def charge(cle):
        appels.append(cle)
        return {"valeur": cle}

    assert cache.get_or_load("a", charge) == {"valeur": "a"}
    assert cache.get_or_load("a", charge) == {"valeur": "a"}
    assert appels == ["a"]


def test_des_cles_differentes_sont_lues_separement():
    appels = []
    cache = ShortLivedCache(ttl_seconds=60, clock=lambda: 1000.0)
    cache.get_or_load("a", lambda k: appels.append(k))
    cache.get_or_load("b", lambda k: appels.append(k))
    assert appels == ["a", "b"]


def test_la_valeur_expire_apres_le_delai():
    appels = []
    maintenant = [1000.0]
    cache = ShortLivedCache(ttl_seconds=5, clock=lambda: maintenant[0])

    def charge(cle):
        appels.append(cle)
        return cle

    cache.get_or_load("a", charge)
    maintenant[0] = 1004.0
    cache.get_or_load("a", charge)
    assert appels == ["a"], "avant expiration, aucune relecture"

    maintenant[0] = 1006.0
    cache.get_or_load("a", charge)
    assert appels == ["a", "a"], "après expiration, relecture"


def test_une_valeur_vide_est_memorisee():
    """Un salarié sans planning ne doit pas être relu à chaque solde."""
    appels = []
    cache = ShortLivedCache(ttl_seconds=60, clock=lambda: 1000.0)

    def charge(cle):
        appels.append(cle)
        return {}

    cache.get_or_load("a", charge)
    cache.get_or_load("a", charge)
    assert appels == ["a"]
