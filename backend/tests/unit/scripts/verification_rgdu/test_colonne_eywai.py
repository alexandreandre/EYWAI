"""Ce que calcule EYWAI : heures et SMIC de référence du mois, ligne de réduction."""
import json
from unittest.mock import patch

import pytest

from scripts.verification_rgdu.colonne_eywai import (
    cumuls_quadra_avant, depuis_le_bac_a_sable, depuis_le_filet,
)
from scripts.verification_rgdu.implicite import SmicImplicite
from scripts.verification_rgdu.quadra_mois import MoisQuadra

pytestmark = pytest.mark.unit

_PROVIDER = "app.modules.payslips.infrastructure.providers.payslip_generator_provider.generate_en_bac_a_sable"


def _mq(mois, cumul_bruts, reduction_mois):
    return MoisQuadra("essai", mois, "MAT", "1990101034019", 0.0, cumul_bruts, 0.0, 0.0, reduction_mois)


def _si(smic_cumule):
    return SmicImplicite(None, smic_cumule, None, False, smic_cumule is not None, "")


def test_les_heures_du_mois_sont_la_difference_des_cumuls(tmp_path):
    def entree(h, rg):
        return {"payslip_data": {"structure_cotisations": {"bloc_allegements": [
            {"coti_id": "reduction_generale", "montant_patronal": rg}]}}, "cumuls": {"cumuls": {"heures_remunerees": h}}}
    f = tmp_path / "reference.json"
    f.write_text(json.dumps({"e1/2026-01": entree(159.13, -582.24), "e1/2026-02": entree(331.63, -600.0)}))
    d = depuis_le_filet(f)
    assert d[("e1", 1)].heures_reduction == 159.13
    assert d[("e1", 2)].heures_reduction == 172.5 and d[("e1", 2)].smic == round(172.5 * 12.02, 2)
    assert d[("e1", 2)].reduction_ligne == 600.0


def _faux_resultat(heures_apres, reduction_negative):
    return {
        "payslip_data": {"structure_cotisations": {"bloc_allegements": [
            {"coti_id": "reduction_generale", "montant_patronal": reduction_negative}]}},
        "cumuls": {"cumuls": {"heures_remunerees": heures_apres}},
    }


@patch(_PROVIDER)
def test_bac_a_sable_mois_ordinaire_prend_la_difference_des_cumuls(faux_generate):
    faux_generate.return_value = _faux_resultat(450.0, -50.0)
    cumuls_prec = {"cumuls": {"heures_remunerees": 300.0}}

    res = depuis_le_bac_a_sable("e1", 4, cumuls_prec)

    faux_generate.assert_called_once_with("e1", 2026, 4, cumuls_prec)
    assert res.employee_id == "e1" and res.mois == 4 and res.source == "bac_a_sable"
    assert res.heures_reduction == 150.0
    assert res.smic == round(150.0 * 12.02, 2)
    assert res.reduction_ligne == 50.0


@patch(_PROVIDER)
def test_bac_a_sable_janvier_ignore_les_cumuls_injectes(faux_generate):
    """Le moteur remet `heures_remunerees` à zéro avant d'ajouter janvier
    (payslip_run_common.mettre_a_jour_cumuls, reset des compteurs d'année civile) :
    les cumuls injectés pour janvier — même non nuls, comme ceux reconstruits
    depuis Quadra (étape 5) — ne doivent pas être soustraits."""
    faux_generate.return_value = _faux_resultat(159.13, -20.0)
    cumuls_prec = {"cumuls": {"heures_remunerees": 1200.0}}

    res = depuis_le_bac_a_sable("e1", 1, cumuls_prec)

    assert res.heures_reduction == 159.13
    assert res.smic == round(159.13 * 12.02, 2)


def test_cumuls_quadra_avant_janvier_ne_se_reconstruit_pas():
    """Rien avant janvier ; `depuis_le_bac_a_sable` ignore de toute façon les
    cumuls injectés ce mois-là (garde ci-dessus) — rien à reconstruire."""
    assert cumuls_quadra_avant(1, [_mq(1, 1000.0, 10.0)], {}, {}) is None


def test_cumuls_quadra_avant_sans_mois_precedent_dans_quadra():
    mois_quadra = [_mq(1, 1000.0, 10.0)]
    assert cumuls_quadra_avant(3, mois_quadra, {1: 1200.0, 2: 1250.0}, {}) is None


def test_cumuls_quadra_avant_prefere_la_dsn_complete():
    mois_quadra = [_mq(1, 1000.0, 10.0), _mq(2, 2000.0, 20.0)]
    smic_dsn = {1: 1200.0, 2: 1250.0}
    implicite = {2: _si(999999.0)}  # ne doit pas être utilisé : la DSN est complète

    c = cumuls_quadra_avant(3, mois_quadra, smic_dsn, implicite)

    assert c == {"cumuls": {
        "brut_total": 2000.0,
        "heures_remunerees": round((1200.0 + 1250.0) / 12.02, 2),
        "reduction_generale_patronale": -30.0,
    }}


def test_cumuls_quadra_avant_replie_sur_l_implicite_si_la_dsn_est_incomplete():
    mois_quadra = [_mq(1, 1000.0, 0.0), _mq(2, 2000.0, 30.0)]
    smic_dsn = {2: 1250.0}  # janvier manque : pas de somme fiable
    implicite = {2: _si(2100.0)}

    c = cumuls_quadra_avant(3, mois_quadra, smic_dsn, implicite)

    assert c["cumuls"]["brut_total"] == 2000.0
    assert c["cumuls"]["heures_remunerees"] == round(2100.0 / 12.02, 2)
    assert c["cumuls"]["reduction_generale_patronale"] == -30.0


def test_cumuls_quadra_avant_rend_none_si_ni_dsn_ni_implicite_ne_suffisent():
    mois_quadra = [_mq(2, 2000.0, 30.0)]
    implicite = {2: SmicImplicite(None, None, None, False, False, "non calculable")}
    assert cumuls_quadra_avant(3, mois_quadra, {}, implicite) is None
