"""Tests — date reprise et plafond 15 ans prime métallurgie."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

from app.modules.collective_agreements.rules.schema import (
    CCRulesDocument,
    document_to_engine_rules,
)
from app.modules.collective_agreements.rules.seeds.metallurgie_3248 import (
    METALLURGIE_3248_SEED,
)
from app.modules.collective_agreements.rules.prime_calcul import (
    cap_anciennete_annees,
    compute_anciennete_annees,
    resolve_prime_anciennete_config,
)
from app.modules.payroll.engine.baremes_loader import _enrich_cc_rules_with_seed
from app.modules.payroll.engine.calcul_brut import _prime_anciennete_deja_saisie
from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.prime_anciennete import calculer_ligne_prime_anciennete
from app.shared.seniority_reference import resolve_date_anciennete_prime
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


def _calendrier_plein_mois() -> list[dict]:
    return [
        {
            "date_complete": f"2026-05-{d:02d}",
            "type": "travail",
            "heures": 6.894,
        }
        for d in range(1, 23)
    ]


class TestSeniorityReferencePrime:
    def test_saisie_mensuelle_prime_anciennete_remplace_calcul_auto(self):
        assert _prime_anciennete_deja_saisie(
            [
                {
                    "prime_id": "prime_anciennete",
                    "libelle": "Prime ancienneté",
                    "montant": 172.92,
                }
            ]
        )
        assert not _prime_anciennete_deja_saisie(
            [{"prime_id": "prime_presence", "libelle": "Prime de présence"}]
        )

    def test_seed_complete_une_extraction_metallurgie_partielle(self):
        partial = {
            "prime_anciennete": {
                "eligibilite": {"min_annees": 3},
                "valeurs_point": [
                    {
                        "valeur": 5.83,
                        "zone_type": "national",
                        "departements": [],
                    }
                ],
                "taux_par_classe": {"5": 0.022},
                "base_de_calcul": {"methode": "valeur_du_point"},
            }
        }

        enriched = _enrich_cc_rules_with_seed(partial, "3248")
        prime = enriched["prime_anciennete"]
        resolved = resolve_prime_anciennete_config(
            prime,
            {"identification": {"adresse": {"code_postal": "77140"}}},
        )

        assert prime["eligibilite"]["max_annees"] == 15.0
        assert resolved["valeur_point"] == 5.24

    def test_resolve_date_reprise_prioritaire(self):
        emp = {
            "hire_date": "2020-01-01",
            "seniority_reference_date": "1988-09-01",
        }
        assert resolve_date_anciennete_prime(emp) == "1988-09-01"

    def test_cap_15_ans_metallurgie(self):
        regles = _metallurgie_baremes()["conventions_collectives"]["idcc_3248"]
        prime = regles["prime_anciennete"]
        raw_years = compute_anciennete_annees("1988-09-01", date(2026, 5, 31), mode="floor")
        assert raw_years >= 37
        capped = cap_anciennete_annees(raw_years, prime)
        assert capped == 15.0

    def test_bourmault_golden_mai_2026(self):
        employee = {
            "date_entree": "2020-01-01",
            "seniority_reference_date": "1988-09-01",
            "statut": "Non cadre",
            "duree_hebdomadaire": 35,
            "salaire_base": 2500.0,
            "convention_collective": {"idcc": "3248"},
            "classification_conventionnelle": {"classe_emploi": 5, "coefficient": 5},
        }
        company = {
            "adresse_code_postal": "77000",
            "identification": {"adresse": {"code_postal": "77000"}},
            "parametres_paie": {"effectif": 50},
        }
        ctx = ChargerContexte(employee, company, _metallurgie_baremes())
        ligne = calculer_ligne_prime_anciennete(
            ctx,
            calendrier_saisie=_calendrier_plein_mois(),
            date_debut_periode=date(2026, 5, 1),
            date_fin_periode=date(2026, 5, 31),
        )
        assert ligne is not None
        assert ligne["gain"] == 172.92
