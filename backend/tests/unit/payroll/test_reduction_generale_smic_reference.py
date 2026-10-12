"""[I12] SMIC de référence de la réduction générale : celui du 1er janvier.

Service-public F24542 (ouvert le 12/10/2026, vérifié le 15/06/2026) : le
coefficient se calcule avec « 3 × SMIC calculé pour un an, valeur au 1er janvier
2026 » ; « Il a été décidé de conserver la valeur du Smic applicable au 1er
janvier 2026 » (SMIC annuel 21 876,40 €, soit 12,02 € de l'heure).

Avant : le moteur lisait `reduction_generale.smic_reference_horaire` et, si la
clé manquait, retombait en silence sur le SMIC courant (12,31 € depuis juin) :
coefficient plus haut, réduction sur-évaluée. Le SMIC du 1er janvier se lit
désormais dans l'historique du barème SMIC, à l'année du bulletin.

Sans palier au 1er janvier de l'année, le bulletin n'est plus refusé (12/10/2026,
cap « alerte avec sortie manuelle ») : janvier 2027 ne doit pas bloquer toute la
paie pour une donnée oubliée. La réduction se calcule sur le SMIC connu le plus
proche — la clé dédiée du barème, sinon le palier en vigueur au 1er janvier, sinon
le SMIC courant — et une alerte le dit, au bulletin comme dans la liste du mois.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_reduction_generale import (
    _calculer_smic_de_reference_cumule,
    calculer_reduction_generale,
)
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

HISTORIQUE_2026 = [
    {"date_debut": "2026-01-01", "cas_general": 12.02},
    {"date_debut": "2026-06-01", "cas_general": 12.31},
]


def _contexte(*, year: int = 2026, month: int = 9, historique=None, cle=None):
    ctx = build_test_contexte(salaire_base=2100.0, effectif=10)
    ctx.year, ctx.month = year, month
    ctx.baremes["smic"] = {
        "cas_general": 12.31,
        "smic_horaire_brut": 12.31,
        "historique": HISTORIQUE_2026 if historique is None else historique,
    }
    reduction = dict(ctx.baremes["reduction_generale"])
    reduction.pop("smic_reference_horaire", None)
    if cle is not None:
        reduction["smic_reference_horaire"] = cle
    ctx.baremes["reduction_generale"] = reduction
    return ctx


def _codes(ctx) -> list[str]:
    return [a.get("code") for a in ctx.alertes_baremes if isinstance(a, dict)]


def test_sans_la_cle_dediee_le_smic_est_celui_du_1er_janvier_pas_le_courant():
    ctx = _contexte()
    assert _calculer_smic_de_reference_cumule(ctx, 151.67) == round(12.02 * 151.67, 2)


def test_la_reduction_de_septembre_se_calcule_sur_12_02_et_non_12_31():
    attendu = _contexte(cle=12.02)
    sans_cle = _contexte()
    red_attendue = calculer_reduction_generale(attendu, 2100.0, 151.67)
    red = calculer_reduction_generale(sans_cle, 2100.0, 151.67)
    assert red["montant_patronal"] == red_attendue["montant_patronal"]
    assert red["taux_patronal"] == red_attendue["taux_patronal"]


def _alertes_smic_absent(ctx) -> list[dict]:
    return [a for a in ctx.alertes_baremes if a.get("code") == "smic_reference_reduction_absent"]


def test_janvier_2027_sans_palier_se_calcule_sur_la_cle_dediee_avec_une_alerte():
    # Janvier 2027 : l'historique s'arrête à juin 2026 ; la clé du barème dit 12,02 €.
    ctx = _contexte(year=2027, month=1, cle=12.02)
    red = calculer_reduction_generale(ctx, 2100.0, 151.67)
    attendu = calculer_reduction_generale(_contexte(cle=12.02), 2100.0, 151.67)

    assert red["montant_patronal"] == attendu["montant_patronal"]
    alertes = _alertes_smic_absent(ctx)
    assert len(alertes) == 1, "une seule alerte par bulletin"
    assert alertes[0]["message"] == (
        "SMIC du 1er janvier 2027 absent de l'historique : réduction générale "
        "calculée sur 12,02 € de l'heure, à vérifier."
    )
    assert alertes[0]["severity"] == "warning" and not alertes[0]["critique"]
    assert "smic_reference_reduction_differe" not in _codes(ctx)


def test_sans_cle_dediee_le_palier_en_vigueur_au_1er_janvier_sert_de_repli():
    ctx = _contexte(year=2027, month=1)
    assert _calculer_smic_de_reference_cumule(ctx, 151.67) == round(12.31 * 151.67, 2)
    assert "12,31 € de l'heure" in _alertes_smic_absent(ctx)[0]["message"]


def test_sans_historique_ni_cle_le_smic_courant_sert_de_repli():
    ctx = _contexte(historique=[])
    assert _calculer_smic_de_reference_cumule(ctx, 151.67) == round(12.31 * 151.67, 2)
    assert _alertes_smic_absent(ctx)[0]["message"] == (
        "SMIC du 1er janvier 2026 absent de l'historique : réduction générale "
        "calculée sur 12,31 € de l'heure, à vérifier."
    )


def test_l_alerte_du_smic_absent_se_voit_dans_la_liste_du_mois():
    from app.modules.payslips.infrastructure.payslip_list_meta import payslip_list_meta

    ctx = _contexte(year=2027, month=1, cle=12.02)
    calculer_reduction_generale(ctx, 2100.0, 151.67)
    ligne = payslip_list_meta({"alertes_baremes": ctx.alertes_baremes})
    assert _alertes_smic_absent(ctx)[0]["message"] in ligne["warnings"]


def test_avec_le_palier_du_1er_janvier_aucune_alerte_de_repli():
    ctx = _contexte(cle=12.02)
    calculer_reduction_generale(ctx, 2100.0, 151.67)
    assert "smic_reference_reduction_absent" not in _codes(ctx)


def test_une_cle_dediee_differente_de_l_historique_est_signalee_et_l_historique_l_emporte():
    ctx = _contexte(cle=12.31)
    red = calculer_reduction_generale(ctx, 2100.0, 151.67)
    attendu = calculer_reduction_generale(_contexte(cle=12.02), 2100.0, 151.67)

    assert red["montant_patronal"] == attendu["montant_patronal"]
    alertes = [a for a in ctx.alertes_baremes if a.get("code") == "smic_reference_reduction_differe"]
    assert len(alertes) == 1, "une seule alerte par bulletin"
    assert alertes[0]["message"] == (
        "Réduction générale : le SMIC de référence saisi dans son barème (12,31 €) "
        "diffère du SMIC au 1er janvier 2026 de l'historique du SMIC (12,02 €). "
        "Martine retient 12,02 €. À vérifier avant de valider ce bulletin."
    )


def test_une_cle_dediee_egale_a_l_historique_ne_dit_rien():
    ctx = _contexte(cle=12.02)
    calculer_reduction_generale(ctx, 2100.0, 151.67)
    assert "smic_reference_reduction_differe" not in _codes(ctx)
