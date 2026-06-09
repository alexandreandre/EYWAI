"""Tests simulation moteur complet avec CC métallurgie (3248)."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from unittest.mock import patch

import pytest

from app.modules.payroll.engine.contexte import ChargerContexte
from app.modules.payroll.engine.controles_convention import controle_convention_collective
from app.modules.payroll.engine.simulation import creer_simulation_bulletin
from tests.unit.collective_agreements.fixtures.cc_rules_snapshot import (
    conventions_collectives_snapshot,
)
from tests.unit.payroll.fixtures.baremes_snapshot import baremes_snapshot


def _metallurgie_rules():
    rules = conventions_collectives_snapshot().get("idcc_3248")
    if rules:
        return rules
    from app.modules.collective_agreements.rules.seeds.metallurgie_3248 import (
        METALLURGIE_3248_SEED,
    )
    from app.modules.collective_agreements.rules.schema import (
        CCRulesDocument,
        document_to_engine_rules,
    )

    doc = CCRulesDocument(
        idcc="3248",
        grilles_salaires=[METALLURGIE_3248_SEED.grille],  # type: ignore[list-item]
        prime_anciennete=METALLURGIE_3248_SEED.prime,
    )
    return document_to_engine_rules(doc)


def _baremes_avec_metallurgie():
    baremes = deepcopy(baremes_snapshot())
    cc = conventions_collectives_snapshot()
    cc["idcc_3248"] = _metallurgie_rules()
    baremes["conventions_collectives"] = cc
    return baremes


class TestSimulationCcMetallurgie:
    def test_simulation_manuelle_avec_idcc_utilise_moteur_complet(self):
        baremes = _baremes_avec_metallurgie()
        employee_data = {
            "id": "manual",
            "first_name": "Sim",
            "last_name": "Test",
            "statut": "Non-cadre",
            "duree_hebdomadaire": 35,
            "salaire_base": 2000.0,
            "date_entree": "2015-01-01",
            "convention_collective": {"idcc": "3248", "libelle": "Métallurgie"},
            "classification_conventionnelle": {
                "groupe_emploi": "C",
                "classe_emploi": 6,
                "coefficient": 6,
            },
        }
        company_data = {
            "entreprise": {
                "identification": {"adresse": {"code_postal": "75001"}},
                "adresse_code_postal": "75001",
                "parametres_paie": {"effectif": 50},
            }
        }
        result = creer_simulation_bulletin(
            employee_data=employee_data,
            company_data=company_data,
            baremes=baremes,
            month=4,
            year=2026,
            scenario_params={"salaire_base_override": 2000.0},
        )
        assert result["metadata"]["mode"] == "manual_cc"
        payslip = result["payslip_data"]
        assert payslip.get("salaire_brut") is not None

    def test_alerte_sous_minimum_conventionnel(self):
        baremes = _baremes_avec_metallurgie()
        employee_data = {
            "id": "manual",
            "statut": "Non-cadre",
            "duree_hebdomadaire": 35,
            "salaire_base": 1500.0,
            "date_entree": "2015-01-01",
            "convention_collective": {"idcc": "3248", "libelle": "Métallurgie"},
            "classification_conventionnelle": {"coefficient": 6, "classe_emploi": 6},
        }
        company_data = {
            "adresse_code_postal": "75001",
            "parametres_paie": {"effectif": 50},
        }
        ctx = ChargerContexte(employee_data, company_data, baremes)
        alertes = controle_convention_collective(ctx, 1500.0)
        codes = [a["code"] for a in alertes]
        assert "cc_salaire_sous_minimum" in codes

    @patch(
        "app.modules.payroll.application.simulation_queries.resolve_minimum_salary_value",
        return_value=2129.17,
    )
    def test_apply_cc_minimum_override(self, _mock_min):
        from app.modules.payroll.application.simulation_queries import (
            _apply_cc_minimum_override,
        )

        scenario = {
            "apply_cc_minimum": True,
            "manual_params": {
                "collective_agreement_id": "ag-1",
                "classification_conventionnelle": {"coefficient": 6},
            },
        }
        updated = _apply_cc_minimum_override(scenario, company={"adresse_code_postal": "75001"})
        assert updated["salaire_base_override"] == pytest.approx(2129.17)
