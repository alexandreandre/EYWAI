"""Un avantage en nature entre au brut, puis sort du net à payer. [G15] [G9]

Il a déjà été fourni en nature (repas, logement, prêt à taux réduit) : il porte
cotisations et impôt comme le reste du salaire, mais il n'est pas versé en
argent.

- BOSS, Avantages en nature, § 20 : « La valeur des avantages en nature doit
  figurer sur le bulletin de paie du salarié, pour leur valeur brute. Les règles
  de calcul et de prélèvement des cotisations sont appliquées selon les mêmes
  modalités que pour les autres éléments de rémunération. »
- Net-entreprises, base de connaissances DSN, fiche 827 : « Après détermination
  du salaire net imposable, il sera déduit du salaire net à verser au salarié. »

Le moteur l'ajoutait au brut sans jamais le retirer du net : 50 € d'avantage
faisaient monter le net à payer d'environ 39 € au lieu de le faire baisser
des seules cotisations et de l'impôt dus sur l'avantage.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.documents.bulletin_view import _lignes_hors_brut

from .helpers import (
    build_test_contexte,
    run_bulletin_pipeline_forfait,
    run_bulletin_pipeline_heures,
)

pytestmark = pytest.mark.unit

PRET = {"pret_employeur": {"montant_mensuel": 50.0}}


def _contexte(avantages: dict, **kwargs):
    ctx = build_test_contexte(salaire_base=2000.0, **kwargs)
    ctx.contrat["remuneration"]["avantages_en_nature"] = avantages
    return ctx


def test_l_avantage_du_pret_entre_au_brut_et_sort_du_net_a_payer():
    sans = run_bulletin_pipeline_heures(_contexte({}))
    avec = run_bulletin_pipeline_heures(_contexte(PRET))

    assert avec["brut"] == pytest.approx(sans["brut"] + 50.0)
    assert avec["net_imposable"] > sans["net_imposable"]
    cotisations_sur_l_avantage = (
        avec["total_cotisations_salariales"] - sans["total_cotisations_salariales"]
    )
    # Le salarié ne touche pas l'avantage : il en paie seulement les cotisations.
    assert avec["net_a_payer"] == pytest.approx(
        sans["net_a_payer"] - cotisations_sur_l_avantage, abs=0.01
    )


def test_l_impot_sur_l_avantage_est_retenu_lui_aussi():
    sans = run_bulletin_pipeline_heures(_contexte({}, taux_pas=10.0))
    avec = run_bulletin_pipeline_heures(_contexte(PRET, taux_pas=10.0))

    cotisations = avec["total_cotisations_salariales"] - sans["total_cotisations_salariales"]
    impot = round((avec["net_imposable"] - sans["net_imposable"]) * 0.10, 2)
    assert avec["net_a_payer"] == pytest.approx(
        sans["net_a_payer"] - cotisations - impot, abs=0.02
    )


def test_au_forfait_jours_aussi():
    sans = run_bulletin_pipeline_forfait(
        _contexte({}, statut="Cadre au forfait jour")
    )
    avec = run_bulletin_pipeline_forfait(
        _contexte(PRET, statut="Cadre au forfait jour")
    )

    assert avec["brut"] == pytest.approx(sans["brut"] + 50.0)
    cotisations = avec["total_cotisations_salariales"] - sans["total_cotisations_salariales"]
    assert avec["net_a_payer"] == pytest.approx(
        sans["net_a_payer"] - cotisations, abs=0.01
    )


def test_le_bulletin_montre_la_deduction_au_bas():
    bulletin = {"synthese_net": {"avantages_en_nature": 50.0}}

    lignes = {l["libelle"]: l["montant_salarial"] for l in _lignes_hors_brut(bulletin)}

    assert lignes["Avantages en nature (déduction)"] == pytest.approx(-50.0)


def test_sans_avantage_aucune_ligne_de_deduction():
    lignes = [l["libelle"] for l in _lignes_hors_brut({"synthese_net": {}})]

    assert "Avantages en nature (déduction)" not in lignes
