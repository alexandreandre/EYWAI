"""Classement final des écarts du rejeu (tâche 9, étape 7) : un motif par règle de regles.md.

Montants anonymisés tirés du rejeu de 2026 (salariés A à D).
"""
import pytest

from scripts.verification_rgdu.classement import Contexte, classer
from scripts.verification_rgdu.comparaison import LigneComparee, preclasser
from scripts.verification_rgdu.oracle import Parametres

pytestmark = pytest.mark.unit
P = Parametres()


def _l(mois, q, loi, e=None, source="dsn", note="", variante=None):
    l = LigneComparee("colorplast", "A", mois, q, source, loi, e, 2400.0 * mois, 2031.34 * (mois - 1),
                      smic_loi_variante=variante, note=note)
    l.preclassement = preclasser(l, P)
    l.note = note or l.note
    return l


def test_une_ligne_identique_n_a_rien_a_classer():
    assert classer(_l(3, 2031.34, 2031.34), "R-H1", Contexte()) == ("", "", "")


def test_juin_a_12_31_est_une_erreur_de_quadra_r_f2():
    classe, regle, note = classer(_l(6, 2080.35, 2031.34), "R-H1", Contexte())
    assert (classe, regle) == ("erreur_quadra", "R-F2") and "12,31" in note


def test_juillet_qui_reprend_l_exces_de_juin_est_rattache_a_juin():
    classe, regle, note = classer(_l(7, 1981.95, 2031.34, source="implicite"), "R-H1", Contexte(exces_juin=49.01))
    assert (classe, regle) == ("erreur_quadra", "R-F2") and "reprend l'excès de juin" in note


def test_sans_dsn_un_ecart_de_juillet_a_septembre_est_une_donnee_manquante():
    classe, regle, _ = classer(_l(9, 1989.92, 2031.34, source="implicite"), "R-H1", Contexte())
    assert (classe, regle) == ("donnee_manquante", "R-D1")


def test_janvier_sans_reduction_chez_quadra():
    classe, regle, _ = classer(_l(1, 2012.10, 2031.34), "R-H1", Contexte(societe_sans_reduction_en_janvier=True))
    assert (classe, regle) == ("erreur_quadra", "R-R2")


def test_arret_sans_maintien_quadra_garde_les_heures_structurelles_retirees():
    classe, regle, _ = classer(_l(6, 222.90, 0.0), "R-H4", Contexte())
    assert (classe, regle) == ("erreur_quadra", "R-H4")


def test_smic_mensuel_seul_sans_les_heures_structurelles():
    classe, regle, _ = classer(_l(2, 1823.03, 1910.05), "R-H1", Contexte())
    assert (classe, regle) == ("erreur_quadra", "R-H1")


def test_seul_martine_s_ecarte_sur_un_mois_repris_c_est_une_donnee_du_mois():
    classe, regle, note = classer(_l(8, 2033.10, 2031.34, e=625.04), "R-H2", Contexte())
    assert classe == "donnee_manquante" and "mois repris" in note


def test_martine_verse_le_maintien_que_quadra_n_a_pas_verse():
    classe, regle, _ = classer(_l(9, 249.15, 250.0, e=1329.65), "R-H4", Contexte())
    assert (classe, regle) == ("methode_legale_differente", "R-H4")


def test_sans_loi_calculable_la_donnee_manque():
    classe, regle, _ = classer(_l(5, 1823.03, None, note="bulletin sans salaire du mois"), "R-A2", Contexte())
    assert (classe, regle) == ("donnee_manquante", "R-A2")
