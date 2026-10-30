"""Le fichier d'essai se dit dans l'envoi, et le point de dépôt reste net-entreprises.

Valeurs lues dans la norme livrée avec DSN-VAL 2026.1 (énumérations
« N4DS_Essai » : 01 envoi fichier test, 02 envoi fichier réel ;
« Point_Depot » : 01 Net-entreprises, 02 MSA) et dans les DSN acceptées
du cabinet (005 = 02, 007 = 01).
"""

import pytest

from app.modules.dsn_export.application.builder import build_envoi

pytestmark = pytest.mark.unit


def test_un_envoi_reel_par_defaut():
    rubriques = build_envoi().rubriques
    assert rubriques["S10.G00.00.005"] == "02"
    assert rubriques["S10.G00.00.007"] == "01"


def test_un_envoi_d_essai():
    rubriques = build_envoi(essai=True).rubriques
    assert rubriques["S10.G00.00.005"] == "01"
    # Un essai se dépose aussi sur net-entreprises, jamais à la MSA.
    assert rubriques["S10.G00.00.007"] == "01"


def test_l_ancien_type_test_reste_un_essai_sans_changer_le_point_de_depot():
    rubriques = build_envoi(dsn_type="dsn_test").rubriques
    assert rubriques["S10.G00.00.005"] == "01"
    assert rubriques["S10.G00.00.007"] == "01"
