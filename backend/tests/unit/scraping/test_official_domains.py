"""Tests domaines officiels centralisés."""

from __future__ import annotations

from core.official_domains import host_is_official


def test_gouv_fr_portals_are_official():
    assert host_is_official("https://entreprendre.service-public.gouv.fr/vosdroits/F78")
    assert host_is_official("https://travail-emploi.gouv.fr/les-heures-supplementaires-contreparties")
    assert host_is_official("https://emploi.gouv.fr/foo")
    assert host_is_official("https://boss.gouv.fr/accueil/")


def test_operators_are_official():
    assert host_is_official("https://www.urssaf.fr/smic")
    assert host_is_official("https://www.agirc-arrco.fr/taux")
    assert host_is_official("https://www.unedic.org/reglementation")


def test_legisocial_is_not_official():
    assert not host_is_official("https://www.legisocial.fr/reperes-sociaux/smic.html")


def test_random_blog_is_not_official():
    assert not host_is_official("https://example.com/taux")
