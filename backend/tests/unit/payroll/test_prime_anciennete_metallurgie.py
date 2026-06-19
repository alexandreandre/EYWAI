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
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.prime_anciennete import calculer_ligne_prime_anciennete
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
        "parametres_paie": {"effectif": 50},
    }
    return ChargerContexte(employee, company, _metallurgie_baremes())


def _calendrier_heures(total: float, nb_jours: int = 22) -> list[dict]:
    heures_jour = total / nb_jours
    return [
        {
            "date_complete": f"2026-04-{d:02d}",
            "type": "travail",
            "heures": round(heures_jour, 4),
        }
        for d in range(1, nb_jours + 1)
    ]


DATE_DEBUT = date(2026, 4, 1)
DATE_FIN = date(2026, 4, 30)


class TestPrimeAncienneteMetallurgieGolden:
    def test_bertaud_plein_mois(self):
        ctx = _contexte(date_entree="2018-09-03", classe=4)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            calendrier_saisie=_calendrier_heures(151.67),
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
            calendrier_saisie=_calendrier_heures(153.77),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is not None
        assert ligne["meta"]["plein_mois"] == pytest.approx(112.86, abs=0.02)
        assert ligne["gain"] == pytest.approx(114.42, abs=0.05)

    def test_boissinot_temps_zero(self):
        ctx = _contexte(date_entree="2018-09-03", classe=4)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            calendrier_saisie=[],
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is None

    def test_bourgeois_prorata_hs(self):
        ctx = _contexte(date_entree="2022-06-13", classe=5)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            calendrier_saisie=_calendrier_heures(166.08),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is not None
        assert ligne["meta"]["plein_mois"] == pytest.approx(37.62, abs=0.02)
        assert ligne["gain"] == pytest.approx(41.19, abs=0.05)

    def test_cadre_coutant_exclu(self):
        ctx = _contexte(date_entree="2014-12-15", statut="Cadre", classe=11)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            calendrier_saisie=_calendrier_heures(151.67),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is None

    def test_frouin_moins_trois_ans(self):
        ctx = _contexte(date_entree="2023-07-10", classe=8)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            calendrier_saisie=_calendrier_heures(151.67),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is None

    def test_de_carvalho_niveau_trois_onze_ans(self):
        ctx = _contexte(date_entree="2014-06-26", classe=3)
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            calendrier_saisie=_calendrier_heures(152.16),
            date_debut_periode=DATE_DEBUT,
            date_fin_periode=DATE_FIN,
        )
        assert ligne is not None
        assert ligne["meta"]["plein_mois"] == pytest.approx(109.73, abs=0.02)
        assert ligne["gain"] == pytest.approx(110.08, abs=0.05)
