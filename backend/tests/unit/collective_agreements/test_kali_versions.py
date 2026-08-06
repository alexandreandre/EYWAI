"""Tests du filtrage des versions d'articles KALI (sans appel réseau)."""

import pytest

from app.modules.collective_agreements.infrastructure.kali_client import (
    _article_en_vigueur,
)

pytestmark = pytest.mark.unit

# 2026-08-06 en millisecondes, pour des tests indépendants de la date du jour.
MAINTENANT = 1_785_974_400_000
LOINTAIN = 32_472_144_000_000  # sentinelle « pas de fin » utilisée par KALI


class TestArticleEnVigueur:
    def test_version_en_vigueur_etendue(self):
        article = {"etat": "VIGUEUR_ETEN", "dateFin": LOINTAIN}
        assert _article_en_vigueur(article, MAINTENANT) is True

    def test_version_remplacee_est_ecartee(self):
        """Régression : KALI renvoie la version remplacée à côté de l'actuelle.

        Sur la métallurgie 3248, 67 numéros d'article apparaissaient plusieurs
        fois avec des contenus différents — l'assistant pouvait citer un article
        périmé comme s'il s'appliquait.
        """
        article = {"etat": "REMPLACE", "dateFin": 1_672_531_200_000}
        assert _article_en_vigueur(article, MAINTENANT) is False

    def test_version_abrogee_est_ecartee(self):
        assert _article_en_vigueur({"etat": "ABROGE"}, MAINTENANT) is False

    def test_date_de_fin_passee_est_ecartee(self):
        """Même marquée en vigueur, une version échue ne s'applique plus."""
        article = {"etat": "VIGUEUR", "dateFin": 1_672_531_200_000}
        assert _article_en_vigueur(article, MAINTENANT) is False

    def test_etat_absent_est_conserve(self):
        """On ne retire pas un article faute de métadonnée."""
        assert _article_en_vigueur({"texte": "..."}, MAINTENANT) is True

    def test_date_de_fin_illisible_est_conservee(self):
        article = {"etat": "VIGUEUR", "dateFin": "inconnue"}
        assert _article_en_vigueur(article, MAINTENANT) is True

    def test_sans_date_de_reference_utilise_maintenant(self):
        assert _article_en_vigueur({"etat": "VIGUEUR", "dateFin": LOINTAIN}) is True
