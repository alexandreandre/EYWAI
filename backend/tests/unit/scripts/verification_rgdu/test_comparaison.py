"""Salarié × mois : SMIC de référence selon Quadra, la loi et MARTINE ; impact et pré-classement."""
import pytest

from scripts.verification_rgdu.comparaison import LigneComparee, impact_en_euros, preclasser
from scripts.verification_rgdu.oracle import Parametres

pytestmark = pytest.mark.unit
P = Parametres()


def _l(q, loi, e):
    return LigneComparee("colorplast", "A", 3, q, "dsn", loi, e, 12000.0, 7000.0)


def test_trois_colonnes_egales():
    assert preclasser(_l(2000.0, 2000.0, 2000.0), P) == "identique"


def test_quadra_s_ecarte_de_la_loi_et_eywai_la_suit():
    assert preclasser(_l(2283.0, 2000.0, 2000.0), P) == "a_juger_quadra"


def test_eywai_s_ecarte_de_la_loi_et_quadra_la_suit():
    assert preclasser(_l(2000.0, 2000.0, 1700.0), P) == "erreur_eywai"


def test_sans_la_loi_on_ne_juge_pas():
    assert preclasser(_l(2000.0, None, 2000.0), P) == "donnee_manquante"


def test_l_impact_est_celui_du_seul_smic_du_mois():
    assert impact_en_euros(12000.0, 7000.0, 2000.0, 2000.0, P) == 0.0
    assert impact_en_euros(12000.0, 7000.0, 2000.0, 2283.0, P) > 0


# --- Point non tranché n° 1 (maintien subrogé) : deux lectures légales possibles ---

def _lv(q, loi, e, loi_variante, variante="point_1_subrogation"):
    return LigneComparee(
        "colorplast", "A", 3, q, "dsn", loi, e, 12000.0, 7000.0,
        smic_loi_variante=loi_variante, variante=variante,
    )


def test_quadra_suit_la_variante_et_eywai_la_lecture_principale():
    """Quadra colle à la seconde lecture légale (smic_entier), MARTINE colle à la
    lecture principale (rapport_salaires) : ni l'accord ni le désaccord entre
    Quadra et la loi principale seule ne suffit à juger — la ligne attend
    l'arbitrage d'Alexandre sur le point non tranché, pas un classement muet."""
    l = _lv(2283.0, 2000.0, 2000.0, 2283.0)
    assert preclasser(l, P) == "point_non_tranche"
    assert l.variante == "point_1_subrogation"
    assert l.note
    assert l.impact_quadra != 0.0
    assert l.impact_eywai == 0.0


def test_les_deux_lectures_egales_se_traitent_comme_le_brief():
    """Quand la variante ne diverge pas de la lecture principale (à la tolérance
    près), il n'y a rien à trancher : le classement ordinaire s'applique, sans
    jamais produire « point_non_tranche » pour rien."""
    l = _lv(2000.0, 2000.0, 1700.0, 2000.0)
    assert preclasser(l, P) == "erreur_eywai"


def test_eywai_ne_suit_aucune_lecture_reste_erreur_eywai():
    """Quadra suit l'une des deux lectures légales (ici la variante), mais MARTINE ne
    suit ni l'une ni l'autre : « point_non_tranche » ne doit jamais remplacer
    silencieusement « erreur_eywai » dans ce cas."""
    l = _lv(2283.0, 2000.0, 1700.0, 2283.0)
    assert preclasser(l, P) == "erreur_eywai"


def test_quadra_ne_suit_aucune_lecture_reste_classement_ordinaire():
    """Miroir de la garde ci-dessus : Quadra est hors tolérance quelle que soit la
    lecture retenue (ni la principale, ni la variante). Trancher le point légal ne
    le rapprocherait pas de la loi : la ligne ne doit jamais devenir
    « point_non_tranche » dans ce cas, même si MARTINE suit l'une des deux lectures —
    elle retombe sur le classement ordinaire contre smic_loi, identique à ce que
    donnerait l'absence de variante."""
    l = _lv(2150.0, 2000.0, 2000.0, 2283.0)
    assert preclasser(l, P) == "a_juger_quadra"
    assert preclasser(_l(2150.0, 2000.0, 2000.0), P) == "a_juger_quadra"
