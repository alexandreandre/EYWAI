"""Les adaptateurs conservent le canal des cumuls et les deux blocs de lignes."""
from datetime import date
from unittest.mock import patch

from app.modules.payroll.engine.calcul_brut import _iccp_legale_par_periode
from app.modules.payroll.infrastructure.reference_dixieme import (
    base_de_reference,
    lignes_pour_dixieme,
)
from app.shared.domain.dixieme_conges import calculer_base_dixieme


def test_les_absences_et_les_gains_se_lisent_ensemble():
    lignes = lignes_pour_dixieme({
        "calcul_du_brut": [{"libelle": "Maintien de salaire", "gain": 900.0}],
        "details_absences": [{"libelle": "Absence maladie du 01/09", "perte": 1000.0}],
    })
    assert len(lignes) == 2
    assert calculer_base_dixieme(2900.0, lignes).base == 2800.0


def test_le_code_stable_prime_sur_un_libelle_renomme():
    lignes = lignes_pour_dixieme({"details_absences": [
        {"code": "brut:reduction_hs_absence", "libelle": "Autre présentation", "perte": 100.0},
        {"libelle": "Absence maladie du 01/09", "perte": 1000.0},
    ]})
    assert calculer_base_dixieme(1900.0, lignes).base == 2780.0


def test_un_contrat_range_transmet_son_identifiant_au_lecteur():
    with patch("app.modules.payroll.infrastructure.reference_dixieme.lire_bulletins_reference", return_value=[]) as lire:
        resultat = base_de_reference(None, "salarie-fictif", date(2026, 6, 1), date(2026, 6, 30), lire_cumul=False, contract_period_id="contrat-fictif")
    assert resultat.base is None
    assert lire.call_args.kwargs["contract_period_id"] == "contrat-fictif"


def test_iccp_du_mois_de_sortie_reconstitue_la_maladie_et_exclut_la_prime():
    from types import SimpleNamespace

    ctx = SimpleNamespace(cp_fin_de_contrat={"periode_en_cours": {
        "brut_avant_mois": 2000.0, "droits": 10.0, "restants": 10.0,
    }}, alertes_baremes=[], exit_indemnities=None)
    resultat = _iccp_legale_par_periode(ctx, 2500.0, 0.1, None, None, 1.0, [
        {"libelle": "Absence maladie du 01/09", "perte": 1000.0},
        {"libelle": "Prime de fin d'année", "gain": 500.0},
    ])
    assert resultat.total == 480.0  # 10 % de 2 000 + (2 500 + 800 - 500)


def test_iccp_ne_transforme_pas_un_passe_inconnu_en_zero():
    from types import SimpleNamespace

    ctx = SimpleNamespace(cp_fin_de_contrat={"periode_en_cours": {
        "brut_avant_mois": None, "droits": 10.0, "restants": 10.0,
    }}, alertes_baremes=[], exit_indemnities=None)
    resultat = _iccp_legale_par_periode(ctx, 2500.0, 0.1, None, None, 100.0)
    assert resultat.total == 1000.0
    assert resultat.periodes[0].dixieme is None
