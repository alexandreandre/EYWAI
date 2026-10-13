"""[D1] Un taux de prévoyance saisi en % au lieu d'une fraction : une alerte, pas un refus.

La fiche porte des fractions (0,0078 pour 0,78 %). Saisir « 0,78 / 1,5 / 8 » sur
un cadre à 3 900 € donnait 3 042 € de prévoyance salariale et un net négatif,
sans un mot (exploration B, 13/10/2026). Au-delà de 10 % salarial ou patronal, ou
de 20 % de forfait social, le bulletin dit quoi vérifier ; il se calcule quand
même. Les fiches réelles plafonnent à 4,69 % salarial, 2,5 % patronal et 8 % de
forfait social : aucune n'est touchée.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

CODE = "prevoyance_taux_improbable"


def _ligne(libelle, salarial, patronal, forfait_social):
    return {"id": "prev_1", "base": "brut_plafonne", "libelle": libelle,
            "salarial": salarial, "patronal": patronal, "forfait_social": forfait_social}


def _alertes(statut, lignes):
    ctx = build_test_contexte(
        statut=statut, salaire_base=3900.0,
        specificites_extra={"prevoyance": {"adhesion": True, "lignes_specifiques": lignes}},
    )
    ctx.month = 10
    cotisations, _ = calculer_cotisations(ctx, 3900.0, 0.0, 0.0)
    alertes = [a for a in ctx.alertes_baremes if isinstance(a, dict) and a.get("code") == CODE]
    return cotisations, alertes


def test_cadre_taux_saisis_en_pourcent_est_signale_sans_bloquer():
    cotisations, alertes = _alertes("Cadre", [_ligne("Prévoyance cadre", 0.78, 1.5, 8)])
    # Le calcul suit la fiche : l'alerte ne refuse rien.
    assert any(l.get("coti_id") == "prevoyance_cadre" for l in cotisations)
    assert len(alertes) == 1
    assert alertes[0]["message"] == (
        "Taux de prévoyance de 78 % (salarial), 150 % (patronal) et 800 % (forfait social) "
        "sur la ligne « Prévoyance cadre » : vérifiez la saisie sur la fiche."
    )
    assert alertes[0]["critique"] is False


def test_un_seul_taux_improbable():
    _, alertes = _alertes("Cadre", [_ligne("Prévoyance TA", 0.78, 0.015, 0.08)])
    assert [a["message"] for a in alertes] == [
        "Taux de prévoyance de 78 % (salarial) sur la ligne « Prévoyance TA » : "
        "vérifiez la saisie sur la fiche."
    ]


def test_non_cadre_avec_lignes_de_la_fiche_est_signale_de_meme():
    _, alertes = _alertes("Non-Cadre", [_ligne("Prévoyance non-cadre", 0.0078, 0.125, 0.08)])
    assert [a["message"] for a in alertes] == [
        "Taux de prévoyance de 12,5 % (patronal) sur la ligne « Prévoyance non-cadre » : "
        "vérifiez la saisie sur la fiche."
    ]


def test_une_alerte_par_ligne_fautive():
    _, alertes = _alertes("Cadre", [
        _ligne("Prévoyance TA", 0.78, 0.015, 0.08),
        _ligne("Prévoyance TB", 0.0078, 1.5, 0.08),
    ])
    assert len(alertes) == 2


@pytest.mark.parametrize("statut", ["Cadre", "Non-Cadre"])
def test_taux_en_fraction_ne_sont_pas_signales(statut):
    """Les plus hauts taux des fiches réelles : aucune alerte."""
    _, alertes = _alertes(statut, [_ligne("Prévoyance", 0.046865, 0.025, 0.08)])
    assert alertes == []


def test_seuils_inclus_ne_sont_pas_signales():
    _, alertes = _alertes("Cadre", [_ligne("Prévoyance", 0.10, 0.10, 0.20)])
    assert alertes == []
