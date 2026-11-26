"""Tests golden Excel — prime d'ancienneté métallurgie Deux-Sèvres (IDCC 3248)."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

import pytest

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    document_to_engine_rules,
)
from app.modules.collective_agreements.rules.seeds.metallurgie_3248 import (
    METALLURGIE_3248_SEED,
)
from app.modules.payroll.engine.contexte import ChargerContexte, ContextePaie
from app.modules.payroll.engine.prime_anciennete import calculer_ligne_prime_anciennete
from app.modules.payroll.engine.temps_travail_mois import TempsDuMois
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def _metallurgie_baremes():
    baremes = deepcopy(baremes_snapshot())
    doc = CCRulesDocument(
        idcc="3248",
        grilles_salaires=[METALLURGIE_3248_SEED.grille],  # type: ignore[list-item]
        prime_anciennete=METALLURGIE_3248_SEED.prime,
    )
    cc = baremes.setdefault("conventions_collectives", {})
    cc["idcc_3248"] = document_to_engine_rules(doc)
    return baremes


def _contexte(
    *,
    date_entree: str,
    statut: str = "Non-cadre",
    classe: int,
    cp: str = "79000",
) -> ContextePaie:
    employee = {
        "date_entree": date_entree,
        "statut": statut,
        "duree_hebdomadaire": 35,
        "salaire_base": 2500.0,
        "convention_collective": {"idcc": "3248", "libelle": "Métallurgie"},
        "classification_conventionnelle": {
            "classe_emploi": classe,
            "coefficient": classe,
        },
    }
    company = {
        "adresse_code_postal": cp,
        "identification": {"adresse": {"code_postal": cp}},
        # Les bulletins de référence d'avril 2026 de l'ancien logiciel sont au
        # point de 2025 (5,70 €), une erreur relevée par l'audit du 03/11/2026
        # (le point de 5,80 € vaut pour tous depuis le 06/03/2026) : le cas fixe
        # ce point pour garder la mécanique du prorata vérifiée au centime. Le
        # point du mois : `collective_agreements/test_valeur_point_2026.py`.
        "parametres_paie": {"effectif": 50, "prime_anciennete": {"valeur_point_override": 5.70}},
    }
    return ChargerContexte(employee, company, _metallurgie_baremes())


def _temps(*, heures_sup: float = 0.0, non_payees: float = 0.0) -> TempsDuMois:
    """Le mois tel que le générateur le mesure : heures sup à 25 %, absences non payées."""
    return TempsDuMois(
        unite="heures",
        reference=151.67,
        absences_non_payees=non_payees,
        heures_sup_majorees=heures_sup * 1.25,
    )


DATE_DEBUT = date(2026, 4, 1)
DATE_FIN = date(2026, 4, 30)


class TestPrimeAncienneteMetallurgieGolden:
    """Bulletins d'avril 2026 de l'ancien logiciel (tableur de contrôle).

    L'ancien logiciel proratisait la prime sur 151,67 + heures sup, sans majoration
    (BONNET : 112,86 × 153,77 ÷ 151,67 = 114,42). La CCN, art. 142, veut que la prime
    « supporte […] les majorations pour heures supplémentaires » : Martine compte chaque
    heure sup avec sa majoration (26/11/2026), d'où quelques centimes de plus.
    """

    def test_barumet_plein_mois(self):
        ctx = _contexte(date_entree="2018-09-03", classe=4)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is not None
        assert ligne["gain"] == pytest.approx(77.81, abs=0.02)
        assert ligne["meta"]["ratio_prorata"] == pytest.approx(1.0, abs=0.001)

    def test_bonnet_prorata_hs(self):
        ctx = _contexte(date_entree="2017-03-01", classe=5)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            temps_du_mois=_temps(heures_sup=2.10),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is not None
        assert ligne["meta"]["plein_mois"] == pytest.approx(112.86, abs=0.02)
        # Ancien logiciel : 114,42 (heures sup non majorées).
        assert ligne["gain"] == 114.81

    def test_cavival_temps_zero(self):
        ctx = _contexte(date_entree="2018-09-03", classe=4)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            temps_du_mois=_temps(non_payees=151.67),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is None

    def test_bourgeois_prorata_hs(self):
        ctx = _contexte(date_entree="2022-06-13", classe=5)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            temps_du_mois=_temps(heures_sup=14.41),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is not None
        assert ligne["meta"]["plein_mois"] == pytest.approx(37.62, abs=0.02)
        # Ancien logiciel : 41,19 (heures sup non majorées).
        assert ligne["gain"] == 42.09

    def test_cadre_ferubel_exclu(self):
        ctx = _contexte(date_entree="2014-12-15", statut="Cadre", classe=11)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is None

    def test_lanossy_moins_trois_ans(self):
        ctx = _contexte(date_entree="2023-07-10", classe=8)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is None

    def test_de_dumieux_niveau_trois_onze_ans(self):
        ctx = _contexte(date_entree="2014-06-26", classe=3)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            temps_du_mois=_temps(heures_sup=0.49),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is not None
        assert ligne["meta"]["plein_mois"] == pytest.approx(109.73, abs=0.02)
        # Ancien logiciel : 110,08 (heures sup non majorées).
        assert ligne["gain"] == 110.17
