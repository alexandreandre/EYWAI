"""[H3] Régime social des indemnités de licenciement et de rupture conventionnelle.

Le bulletin de sortie ajoutait l'indemnité au net en totalité, sans limite,
sans CSG/CRDS sur la part au-delà du minimum, sans la contribution patronale
de 40 % de la rupture conventionnelle ; la DSN n'avait pas de code 093 ; le
dossier écrivait un « total net estimé » égal au brut.

Sources ouvertes le 11/10/2026 :
- BOSS, « Indemnités de rupture » (mis à jour le 26/06/2026) :
  § 50 et 60 : exclusion de l'assiette des cotisations pour la fraction non
  imposable (CGI 80 duodecies), dans la limite de 2 PASS ;
  § 70 : indemnités supérieures à 10 PASS soumises dès le premier euro ;
  § 80 : CSG et CRDS non dues dans la limite du plus faible du montant légal ou
  conventionnel et du montant exclu des cotisations ; pas d'abattement pour
  frais professionnels ;
  § 300 : fraction non imposable d'une indemnité de licenciement = le plus élevé
  du double de la rémunération annuelle brute de l'année civile précédente, de
  la moitié de l'indemnité (ces deux limites dans la limite de 6 PASS) et du
  montant légal ou conventionnel ; exemples chiffrés du § 380 (60 000 € et
  138 000 €) ;
  § 950 et 970 : rupture conventionnelle, mêmes limites ; exemple de 19 000 € ;
  § 1000 : « contribution patronale spécifique […] dont le taux est fixé à 40 %,
  sur la partie exclue de l'assiette de cotisations sociales. Le forfait social
  n'est pas dû sur les indemnités de rupture conventionnelle. »
- Code de la sécurité sociale, art. L137-12 (Légifrance, version en vigueur
  depuis le 31/12/2025, modifiée par la loi n° 2025-1403 du 30 décembre 2025,
  art. 15) : « Le taux de cette contribution est fixé à 40 %. »
- Cahier technique DSN 2026.1 (copie locale
  docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt, rubrique
  S21.G00.81.001, l. 18278) : « 093 - Contribution sur indemnités de mise à la
  retraite ou de rupture conventionnelle individuelle », code Urssaf.
- PASS 2026 : 48 060 € (BOSS, exemples du § 380 ; barème `pss` de la base).
"""

from __future__ import annotations

import copy
from unittest.mock import patch

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.payroll.engine.bulletin import creer_bulletin_sortie
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from app.modules.payroll.engine.regime_indemnites_rupture import ventiler_indemnite_de_rupture
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit

PASS_2026 = 48060.0
_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"


def test_licenciement_de_60_000_euros_exemple_du_boss():
    regime = ventiler_indemnite_de_rupture(
        "licenciement", 60000.0, minimum=50000.0, remuneration_annuelle_n_1=24000.0, pass_annuel=PASS_2026
    )
    assert regime.exoneree_impot == 50000.0
    assert regime.exoneree_cotisations == 50000.0
    assert regime.soumise_cotisations == 10000.0
    assert regime.exoneree_csg == 50000.0
    assert regime.assiette_csg_seule == 0.0
    assert regime.contribution_patronale == 0.0


def test_licenciement_de_138_000_euros_plafonne_a_deux_pass():
    regime = ventiler_indemnite_de_rupture(
        "licenciement", 138000.0, minimum=120000.0, remuneration_annuelle_n_1=250000.0, pass_annuel=PASS_2026
    )
    assert regime.exoneree_impot == 138000.0
    assert regime.exoneree_cotisations == 96120.0
    assert regime.soumise_cotisations == 41880.0
    assert regime.exoneree_csg == 96120.0
    assert regime.assiette_csg_seule == 0.0


def test_rupture_conventionnelle_de_19_000_euros_csg_au_dela_du_minimum_et_contribution_de_40():
    regime = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 19000.0, minimum=8000.0, remuneration_annuelle_n_1=30000.0,
        pass_annuel=PASS_2026,
    )
    assert regime.exoneree_cotisations == 19000.0
    assert regime.soumise_cotisations == 0.0
    assert regime.exoneree_csg == 8000.0
    assert regime.assiette_csg_seule == 11000.0
    assert regime.contribution_patronale == 7600.0


@pytest.mark.parametrize(
    "montant,contribution",
    # Deux ruptures conventionnelles de mars 2026 déclarées par un cabinet
    # (DSN, bloc 81, code 093 à 40,000 %) : 1 005,82 et 7 351,60.
    [(2514.55, 1005.82), (18379.00, 7351.60)],
)
def test_contribution_patronale_au_centime_des_dsn_de_mars_2026(montant, contribution):
    regime = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", montant, minimum=1000.0, remuneration_annuelle_n_1=40000.0,
        pass_annuel=PASS_2026,
    )
    assert regime.contribution_patronale == contribution


def test_au_dela_de_dix_pass_tout_est_soumis():
    regime = ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 500000.0, minimum=100000.0, remuneration_annuelle_n_1=300000.0,
        pass_annuel=PASS_2026,
    )
    assert regime.exoneree_cotisations == 0.0
    assert regime.soumise_cotisations == 500000.0
    assert regime.exoneree_csg == 0.0
    assert regime.contribution_patronale == 0.0


def _salarie() -> dict:
    return {
        "id": "emp-1",
        "hire_date": "2020-01-01",
        "contract_type": "CDI",
        "salaire_de_base": {"valeur": 2400.0},
        "baremes": {"pss": {"annuel": PASS_2026, "mensuel": 4005.0}},
    }


def _rupture(**extra) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "rupture_conventionnelle",
        "exit_request_date": "2026-09-15",
        "last_working_day": "2026-10-31",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        "montant_negocie": 15000.0,
        **extra,
    }


def _base_n_1() -> BaseEnMemoire:
    # Rémunération de l'année civile précédente, lue sur les cumuls de décembre.
    return BaseEnMemoire(
        {
            "employee_schedules": [
                {
                    "employee_id": "emp-1",
                    "year": 2025,
                    "month": 12,
                    "cumuls": {"cumuls": {"brut_annee_civile": 30000.0}},
                }
            ]
        }
    )


@patch(_ICCP, return_value={"montant": 0.0, "description": "ICCP", "details": {}})
def test_le_dossier_ventile_l_indemnite_et_ne_dit_plus_un_net_egal_au_brut(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _rupture(), _base_n_1())

    rc = dossier["indemnite_rupture_conventionnelle"]
    regime = rc["regime_social"]
    assert regime["remuneration_annuelle_n_1"] == 30000.0
    assert regime["exoneree_cotisations"] == 15000.0
    assert regime["contribution_patronale"] == 6000.0
    assert regime["assiette_csg_seule"] == round(15000.0 - rc["montant_minimum"], 2)
    assert dossier["total_net_indemnities"] is None


def _baremes_de_la_base() -> dict:
    """Le barème de test, avec la CSG telle que la base la porte : une entrée
    « csg » à 6,8 % déductible et 2,9 % non déductible (CRDS comprise)."""
    baremes = copy.deepcopy(baremes_snapshot())
    cle = next(k for k, v in baremes["cotisations"].items() if isinstance(v, list))
    lignes = [
        c for c in baremes["cotisations"][cle] if c.get("id") not in ("csg_deductible", "csg_non_deductible", "crds")
    ]
    lignes.append(
        {"id": "csg", "libelle": "CSG/CRDS", "base": "brut", "salarial": {"deductible": 0.068, "non_deductible": 0.029}}
    )
    baremes["cotisations"][cle] = lignes
    return baremes


def _contexte_de_sortie(regime: dict, montant: float):
    contexte = build_test_contexte(salaire_base=2400.0, baremes=_baremes_de_la_base())
    contexte.exit_indemnities = {
        "indemnite_rupture_conventionnelle": {
            "montant": montant,
            "montant_negocie": montant,
            "montant_minimum": regime["exoneree_csg"],
            "regime_social": regime,
        }
    }
    return contexte


def _regime_15000() -> dict:
    return ventiler_indemnite_de_rupture(
        "rupture_conventionnelle", 15000.0, minimum=4000.0, remuneration_annuelle_n_1=30000.0,
        pass_annuel=PASS_2026,
    ).en_dict()


def test_le_bulletin_porte_la_csg_crds_au_dela_du_minimum_et_la_contribution_de_40():
    contexte = _contexte_de_sortie(_regime_15000(), 15000.0)
    lignes, _total = calculer_cotisations(contexte, 2400.0)

    par_libelle = {l["libelle"]: l for l in lignes}
    csg = par_libelle["CSG/CRDS non déductible sur indemnité de rupture non imposable"]
    assert csg["base"] == 11000.0
    assert csg["montant_salarial"] == round(11000.0 * 0.097, 2)
    contribution = par_libelle["Contribution patronale sur indemnité de rupture conventionnelle (40 %)"]
    assert contribution["base"] == 15000.0
    assert contribution["montant_patronal"] == 6000.0
    assert contribution["coti_id"] == "contribution_indemnite_rupture"


def test_le_bulletin_dit_la_limite_calculee_et_ajoute_la_part_exoneree_au_net():
    regime = _regime_15000()
    contexte = _contexte_de_sortie(regime, 15000.0)
    nets = {"net_a_payer": 1900.0, "net_imposable": 1900.0, "montant_net_social": 1900.0}
    bulletin = creer_bulletin_sortie(contexte, 2400.0, [], [], nets, [], contexte.exit_indemnities, 2026, 10)

    (ligne,) = bulletin["indemnites_sortie"]["lignes_exonerees"]
    assert ligne["montant"] == 15000.0
    assert "dans la limite légale" not in ligne["note"]
    assert "15 000,00" in ligne["note"] and "11 000,00" in ligne["note"]
    assert bulletin["net_a_payer"] == round(1900.0 + 15000.0, 2)


def test_sans_regime_calcule_le_bulletin_ne_promet_pas_de_limite():
    contexte = build_test_contexte(salaire_base=2400.0)
    contexte.exit_indemnities = {
        "indemnite_rupture_conventionnelle": {"montant": 15000.0, "montant_negocie": 15000.0}
    }
    nets = {"net_a_payer": 1900.0, "net_imposable": 1900.0, "montant_net_social": 1900.0}
    bulletin = creer_bulletin_sortie(contexte, 2400.0, [], [], nets, [], contexte.exit_indemnities, 2026, 10)

    (ligne,) = bulletin["indemnites_sortie"]["lignes_exonerees"]
    assert "dans la limite légale" not in ligne["note"]
    assert "recalculez" in ligne["note"].lower()
    assert "dans la limite du montant légal" not in bulletin["note_sortie"]


def test_la_dsn_declare_la_contribution_en_093_sur_la_base_03_a_40():
    contexte = _contexte_de_sortie(_regime_15000(), 15000.0)
    lignes, _total = calculer_cotisations(contexte, 2400.0)

    _bases, cotisations, _avert = build_bases_and_cotisations(
        lignes, brut=2400.0, period_start="01102026", period_end="31102026"
    )
    (c093,) = [c for c in cotisations if c.code == "093"]
    assert c093.rubriques["_base"] == "03"
    assert c093.rubriques["S21.G00.81.003"] == "15000.00"
    assert c093.rubriques["S21.G00.81.004"] == "6000.00"
    assert c093.rubriques["S21.G00.81.007"] == "40.000"
