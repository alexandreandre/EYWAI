"""SMIC que Quadra a implicitement retenu, reconstitué depuis sa réduction cumulée."""
import pytest

from scripts.verification_rgdu.implicite import smic_quadra_par_mois
from scripts.verification_rgdu.oracle import Parametres, reduction_cumulee
from scripts.verification_rgdu.quadra_mois import MoisQuadra

pytestmark = pytest.mark.unit
P = Parametres()


def _m(mois, brut_mois, cumul_bruts, reduction_mois, entree=None):
    return MoisQuadra(
        "colorplast", mois, "ESSAI", "1999999999999", brut_mois, cumul_bruts, 0.0, 0.0,
        reduction_mois, entree=entree,
    )


def test_deux_mois_redonnent_les_smic_du_mois():
    """Test du brief, adapté à la nouvelle sortie. Janvier porte l'exception du
    premier mois (smic_mois = smic_cumule) ; février se déduit par différence des
    deux SMIC cumulés."""
    r1 = reduction_cumulee(3000.0, 2300.0, P)
    r2 = reduction_cumulee(6100.0, 4550.0, P) - r1
    smic = smic_quadra_par_mois([_m(1, 3000.0, 3000.0, r1), _m(2, 3100.0, 6100.0, r2)], P)
    assert smic[1].calculable and smic[2].calculable
    # Le coefficient arrondi à 4 décimales laisse un palier d'environ 0,4 € de SMIC par mois.
    assert abs(smic[1].smic_mois - 2300.0) < 1.0
    assert abs(smic[2].smic_mois - 2250.0) < 1.5
    assert smic[1].smic_mois == smic[1].smic_cumule


def test_une_reduction_cumulee_nulle_ou_negative_n_est_pas_calculable():
    smic = smic_quadra_par_mois([_m(1, 1000.0, 1000.0, 0.0)], P)
    assert smic[1].calculable is False
    assert smic[1].smic_mois is None
    assert smic[1].raison


def test_un_mois_hors_de_portee_rend_aussi_le_mois_suivant_non_calculable():
    """La réduction voulue du premier mois (900 €) dépasse le maximum atteignable sur
    ce brut cumulé (1000 € × Tmax ≈ 398,10 €, exemple de `test_oracle.py`) :
    `ValueError` interceptée, mois non calculable. Le second mois, bien
    qu'atteignable sur son propre brut cumulé (3000 € × Tmax ≈ 1194,30 €, cible
    cumulée 950 €), n'a plus de SMIC cumulé de départ : non calculable aussi,
    faute de départ."""
    mois = [_m(1, 1000.0, 1000.0, 900.0), _m(2, 2000.0, 3000.0, 50.0)]
    smic = smic_quadra_par_mois(mois, P)
    assert smic[1].calculable is False
    assert smic[1].smic_mois is None
    assert smic[1].raison
    assert smic[2].calculable is False
    assert smic[2].smic_mois is None
    assert smic[2].raison


def test_un_mois_sous_le_plancher_est_signale():
    """Réduction de 10 € sur un brut cumulé de 1000 € : le plancher (Tmin × brut)
    vaut 20 €, aucune réduction légale n'existe strictement entre 0 et ce plancher —
    signalé par `sous_le_plancher`, mais le mois reste calculable (pas d'erreur)."""
    smic = smic_quadra_par_mois([_m(1, 1000.0, 1000.0, 10.0)], P)
    assert smic[1].calculable is True
    assert smic[1].sous_le_plancher is True


def test_un_cumul_hors_palier_est_calculable_avec_un_ecart_non_nul():
    """Cumul et cible réels (exemple de la tâche 2, `test_oracle.py`) : la réduction
    ne tombe presque jamais pile sur un palier de la formule (coefficient arrondi à
    4 décimales) — ce n'est pas une erreur, `ecart_au_palier` mesure l'écart."""
    smic = smic_quadra_par_mois([_m(1, 23688.83, 23688.83, 4408.07)], P)
    assert smic[1].calculable is True
    assert smic[1].ecart_au_palier != 0.0


def test_un_premier_mois_de_presence_en_mars_porte_son_propre_smic_cumule():
    """Salarié entré en mars (date d'entrée connue sur le bulletin) : aucun mois
    avant lui dans les données, et ce n'est pas janvier. L'exception s'applique
    quand même (entrée détectée) : smic_mois = smic_cumule, comme pour janvier."""
    smic = smic_quadra_par_mois([_m(3, 2000.0, 2000.0, 400.0, entree="15/03/2026")], P)
    assert smic[3].calculable is True
    assert smic[3].smic_mois == smic[3].smic_cumule


def test_un_premier_mois_sans_entree_ni_janvier_reste_calculable_sans_smic_du_mois():
    """Cas limite décidé pour ce module : si le relevé fourni commence à un mois qui
    n'est ni janvier ni un mois d'entrée connue (ex. données manquantes pour les
    mois d'avant, salarié déjà présent), le SMIC cumulé du mois est calculable mais
    son SMIC du mois propre ne l'est pas : on ne sait pas ce qui s'est accumulé
    avant, et ce n'est pas une vraie entrée — mieux vaut l'admettre que deviner."""
    smic = smic_quadra_par_mois([_m(4, 2000.0, 2000.0, 400.0)], P)
    assert smic[4].calculable is True
    assert smic[4].smic_mois is None
    assert smic[4].smic_cumule is not None
    assert smic[4].raison


def test_la_chaine_se_reamorce_apres_un_mois_non_calculable_par_cascade():
    """Un troisième mois, après le mois « non calculable par cascade » du test
    précédent, redevient calculable normalement : il dispose du SMIC cumulé du
    mois qui le précède (mémorisé en interne même si ce mois-là n'a pas été publié
    comme calculable)."""
    mois = [
        _m(1, 1000.0, 1000.0, 900.0),   # hors de portée : non calculable
        _m(2, 2000.0, 3000.0, 50.0),    # cascade : non calculable, faute de départ
        _m(3, 2000.0, 5000.0, 50.0),    # redevient calculable : SMIC cumulé du mois 2 connu en interne
    ]
    smic = smic_quadra_par_mois(mois, P)
    assert smic[1].calculable is False
    assert smic[2].calculable is False
    assert smic[3].calculable is True
    assert smic[3].smic_mois is not None
