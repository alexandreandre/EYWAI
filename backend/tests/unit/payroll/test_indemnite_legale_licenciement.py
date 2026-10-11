"""[H4] Indemnité légale de licenciement : salaire de référence tiré des bulletins,
ancienneté à la fin du préavis, minimum de la rupture conventionnelle contrôlé.

Le dossier prenait le salaire de base (un 39 h de Colorplast perd ses heures
structurelles et sa prime d'ancienneté, 20 à 30 % du brut) et l'ancienneté au
dernier jour travaillé ; un montant de rupture conventionnelle sous le minimum
était accepté sans rien dire.

Sources ouvertes le 11/10/2026 :
- Code du travail, art. R1234-4 (Légifrance, en vigueur depuis le 27/09/2017) :
  « selon la formule la plus avantageuse pour le salarié : 1° Soit la moyenne
  mensuelle des douze derniers mois précédant le licenciement, ou lorsque la
  durée de service du salarié est inférieure à douze mois, la moyenne mensuelle
  de la rémunération de l'ensemble des mois précédant le licenciement ; 2° Soit
  le tiers des trois derniers mois. Dans ce cas, toute prime ou gratification
  de caractère annuel ou exceptionnel […] n'est prise en compte que dans la
  limite d'un montant calculé à due proportion. »
- Code du travail, art. R1234-1 (en vigueur depuis le 27/09/2017) : « En cas
  d'année incomplète, l'indemnité est calculée proportionnellement au nombre de
  mois complets. » ; art. R1234-2 : un quart de mois par année jusqu'à dix ans,
  un tiers au-delà.
- Code du travail, art. L1234-4 (en vigueur depuis le 01/05/2008) :
  « L'inexécution du préavis de licenciement n'a pas pour conséquence d'avancer
  la date à laquelle le contrat prend fin. »
- service-public.gouv.fr F987 (vérifié le 05/06/2026) : salaires bruts ;
  « L'ancienneté est calculée jusqu'à la date de rupture effective du contrat
  de travail, c'est-à-dire à la fin du préavis » ; les 8 mois d'ancienneté
  s'apprécient « à la date d'envoi de la lettre de licenciement ».
- BOSS, « Indemnités de rupture » (mis à jour le 26/06/2026), § 840 à 870 et
  § 1010 : la rupture conventionnelle ne peut être inférieure à l'indemnité
  légale (ou conventionnelle) de licenciement ; sous 8 mois d'ancienneté, au
  prorata : (salaire de référence × 1/4) × nombre de mois / 12.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import calculer_indemnites_sortie
from tests.unit.base_en_memoire import BaseEnMemoire

pytestmark = pytest.mark.unit

_ICCP = "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
_SANS_ICCP = {"montant": 0.0, "description": "ICCP", "details": {}}
_BAREMES = {"pss": {"annuel": 48060.0, "mensuel": 4005.0}}


def _salarie(hire_date: str = "2021-08-23") -> dict:
    return {
        "id": "emp-1",
        "hire_date": hire_date,
        "contract_type": "CDI",
        "duree_hebdomadaire": 39,
        "salaire_de_base": {"valeur": 2374.55},
        "specificites_paie": {"salaire_hors_hs_structurelles": True},
        "baremes": _BAREMES,
    }


def _bulletin(annee: int, mois: int, brut: float, lignes: list | None = None) -> dict:
    return {
        "employee_id": "emp-1",
        "year": annee,
        "month": mois,
        "payslip_data": {
            "salaire_brut": brut,
            "calcul_du_brut": lignes or [{"libelle": "Salaire de base", "gain": brut}],
        },
    }


def _douze_mois(derniers: tuple = (3100.00, 3168.27, 3050.00), dernier_bulletin=None) -> BaseEnMemoire:
    """Septembre 2025 à août 2026 : neuf mois à 3 000 €, puis les trois derniers."""
    bulletins = [_bulletin(2025, m, 3000.0) for m in (9, 10, 11, 12)]
    bulletins += [_bulletin(2026, m, 3000.0) for m in (1, 2, 3, 4, 5)]
    bulletins += [_bulletin(2026, 6, derniers[0]), _bulletin(2026, 7, derniers[1])]
    bulletins.append(dernier_bulletin or _bulletin(2026, 8, derniers[2]))
    return BaseEnMemoire({"payslips": bulletins})


def _licenciement(**extra) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "licenciement",
        "exit_request_date": "2026-09-01",
        "last_working_day": "2026-10-31",
        "notice_period_days": 60,
        "notice_end_date": "2026-10-31",
        "notice_indemnity_type": "executed",
        **extra,
    }


@patch(_ICCP, return_value=_SANS_ICCP)
def test_le_salaire_de_reference_est_le_plus_favorable_des_douze_ou_trois_derniers_bruts(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _licenciement(), _douze_mois())

    moyenne_12 = round((9 * 3000.0 + 3100.00 + 3168.27 + 3050.00) / 12, 2)
    tiers_3 = round((3100.00 + 3168.27 + 3050.00) / 3, 2)
    assert tiers_3 > moyenne_12
    assert dossier["salaire_reference"] == tiers_3
    details = dossier["calculation_details"]
    assert details["salaire_ref_12_mois"] == moyenne_12
    assert details["salaire_ref_3_mois"] == tiers_3


@patch(_ICCP, return_value=_SANS_ICCP)
def test_une_prime_annuelle_des_trois_derniers_mois_compte_a_due_proportion(_iccp):
    aout = _bulletin(
        2026,
        8,
        4250.0,
        [
            {"libelle": "Salaire de base", "gain": 3050.0},
            {"libelle": "Prime exceptionnelle", "gain": 1200.0},
        ],
    )
    dossier = calculer_indemnites_sortie(_salarie(), _licenciement(), _douze_mois(dernier_bulletin=aout))

    tiers_3 = round((3100.00 + 3168.27 + 3050.00 + 1200.0 * 3 / 12) / 3, 2)
    assert dossier["calculation_details"]["salaire_ref_3_mois"] == tiers_3


@patch(_ICCP, return_value=_SANS_ICCP)
def test_l_anciennete_court_jusqu_a_la_fin_du_preavis_meme_dispense_en_mois_complets(_iccp):
    # Dispensé dès le 30/09 : le contrat finit quand même le 31/10 (L1234-4).
    depart = _licenciement(last_working_day="2026-09-30", notice_indemnity_type="paid")
    dossier = calculer_indemnites_sortie(_salarie(), depart, _douze_mois())

    # Du 23/08/2021 au 31/10/2026 : 5 ans et 2 mois complets.
    assert dossier["calculation_details"]["anciennete_mois"] == 62
    assert dossier["calculation_details"]["fin_du_contrat"] == "2026-10-31"
    reference = dossier["salaire_reference"]
    assert dossier["indemnite_licenciement"]["montant"] == round(reference * (62 / 12) / 4, 2)


@patch(_ICCP, return_value=_SANS_ICCP)
def test_les_huit_mois_s_apprecient_a_la_notification(_iccp):
    depart = _licenciement(
        exit_request_date="2026-09-10",
        last_working_day="2026-10-09",
        notice_period_days=30,
        notice_end_date="2026-10-10",
    )
    # Entrée le 15/01/2026 : 7 mois à la notification, 8 à la fin du préavis.
    dossier = calculer_indemnites_sortie(_salarie("2026-01-15"), depart, _douze_mois())

    assert dossier["indemnite_licenciement"]["montant"] == 0.0


def _rupture(**extra) -> dict:
    return {
        "id": "exit-1",
        "exit_type": "rupture_conventionnelle",
        "exit_request_date": "2026-09-01",
        "last_working_day": "2026-10-31",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
        **extra,
    }


@patch(_ICCP, return_value=_SANS_ICCP)
def test_sous_huit_mois_la_rupture_conventionnelle_a_un_minimum_au_prorata(_iccp):
    dossier = calculer_indemnites_sortie(_salarie("2026-04-01"), _rupture(), _douze_mois())

    rc = dossier["indemnite_rupture_conventionnelle"]
    reference = dossier["salaire_reference"]
    # Du 01/04/2026 au 31/10/2026 inclus : 7 mois complets.
    assert rc["montant_minimum"] == round(reference / 4 * 7 / 12, 2)


@patch(_ICCP, return_value=_SANS_ICCP)
def test_une_rupture_conventionnelle_sous_le_minimum_legal_est_signalee(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _rupture(montant_negocie=1000.0), _douze_mois())

    rc = dossier["indemnite_rupture_conventionnelle"]
    assert rc["montant_negocie"] == 1000.0
    assert rc["montant_minimum"] > 1000.0
    assert any("inférieur au minimum légal" in a for a in rc["alertes"])


@patch(_ICCP, return_value=_SANS_ICCP)
def test_sans_bulletin_la_reference_est_le_salaire_habituel_du_contrat_et_c_est_dit(_iccp):
    dossier = calculer_indemnites_sortie(_salarie(), _licenciement(), BaseEnMemoire({}))

    assert dossier["salaire_reference"] > 2374.55
    assert any("Aucun bulletin" in a for a in dossier["indemnite_licenciement"]["alertes"])
