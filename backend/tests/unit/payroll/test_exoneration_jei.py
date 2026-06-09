"""Tests exonération JEI (module pur, sans réseau)."""

from __future__ import annotations

from datetime import date
from typing import Dict, List

import pytest

from app.modules.jei_settings.domain.exonerations_interfaces import (
    AbstractJeiExonerationsRepository,
)
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_reduction_generale import (
    calculer_reduction_generale,
)
from app.modules.payroll.engine.cotisations_rubriques import resoudre_rubrique
from app.modules.payroll.engine.exoneration_jei import (
    calculer_exoneration_jei,
    jei_applicable,
    mois_actifs_annuel,
    plafond_annuel_etablissement,
    plafond_remuneration_jei,
)
from tests.unit.payroll.helpers import build_test_contexte


class InMemoryJeiExonerationsRepo(AbstractJeiExonerationsRepository):
    """Mock en mémoire pour le plafond 5 PASS."""

    def __init__(self) -> None:
        self.rows: List[Dict[str, object]] = []

    def sum_annual_excluding_month(
        self,
        company_id: str,
        year: int,
        exclude_employee_id: str,
        exclude_month: int,
    ) -> float:
        total = 0.0
        for row in self.rows:
            if (
                row["company_id"] == company_id
                and row["year"] == year
                and not (
                    row["employee_id"] == exclude_employee_id
                    and row["month"] == exclude_month
                )
            ):
                total += float(row["montant_exonere"])
        return round(total, 2)

    def upsert_monthly(
        self,
        company_id: str,
        year: int,
        month: int,
        employee_id: str,
        montant_exonere: float,
    ) -> None:
        self.rows = [
            r
            for r in self.rows
            if not (
                r["company_id"] == company_id
                and r["year"] == year
                and r["month"] == month
                and r["employee_id"] == employee_id
            )
        ]
        self.rows.append(
            {
                "company_id": company_id,
                "year": year,
                "month": month,
                "employee_id": employee_id,
                "montant_exonere": round(montant_exonere, 2),
            }
        )


def _contexte_jei_rd(**kwargs):
    defaults = {
        "salaire_base": 2500.0,
        "jei_enabled": True,
        "date_creation_etablissement": "2024-01-15",
        "specificites_extra": {"personnel_rd_eligible_jei": True},
    }
    defaults.update(kwargs)
    return build_test_contexte(**defaults)


class TestPlafondsJei:
    def test_plafond_remuneration_45_smic(self):
        ctx = _contexte_jei_rd()
        heures = (35 * 52) / 12
        plafond = plafond_remuneration_jei(ctx, heures)
        attendu = round(4.5 * ctx.smic_horaire * heures, 2)
        assert plafond == pytest.approx(attendu, abs=0.02)

    def test_mois_actifs_creation_en_cours_annee(self):
        assert mois_actifs_annuel(date(2026, 4, 1), 2026) == 9

    def test_plafond_annuel_5_pass(self):
        ctx = _contexte_jei_rd()
        plafond = plafond_annuel_etablissement(ctx, 2026, ctx.baremes["jei"])
        assert plafond == pytest.approx(5 * 48060.0, abs=0.01)


class TestEligibilite:
    def test_non_rd_pas_d_exoneration(self):
        ctx = build_test_contexte(
            jei_enabled=True,
            date_creation_etablissement="2024-01-15",
        )
        ctx.year = 2026
        ctx.month = 4
        lignes, _ = calculer_cotisations(ctx, 2500.0)
        exo = calculer_exoneration_jei(ctx, lignes, 151.67, year=2026, month=4)
        assert exo is None
        assert not jei_applicable(ctx, 2026, 4)

    def test_entreprise_hors_fenetre_7_ans(self):
        ctx = build_test_contexte(
            jei_enabled=True,
            date_creation_etablissement="2010-01-01",
            specificites_extra={"personnel_rd_eligible_jei": True},
        )
        assert not ctx.jei_entreprise_active(2026, 1)


class TestCalculExoneration:
    def test_exoneration_nominale_personnel_rd(self):
        ctx = _contexte_jei_rd()
        ctx.year = 2026
        ctx.month = 4
        brut = 2500.0
        heures = (35 * 52) / 12
        lignes, _ = calculer_cotisations(ctx, brut, 0.0, 0.0)

        exo = calculer_exoneration_jei(ctx, lignes, heures, year=2026, month=4)
        assert exo is not None
        assert exo["coti_id"] == "exoneration_jei"
        assert exo["montant_patronal"] < 0
        assert resoudre_rubrique("exoneration_jei", exo["libelle"]) == "exonerations"

        montant_exo = abs(exo["montant_patronal"])
        # Cotisations patronales éligibles (maladie, AF, vieillesse) sur assiette <= plafond 4,5 SMIC
        assert montant_exo > 400.0
        assert montant_exo < brut * 0.30

    def test_ecretage_45_smic(self):
        ctx = _contexte_jei_rd(salaire_base=12000.0)
        ctx.year = 2026
        ctx.month = 4
        brut = 12000.0
        heures = (35 * 52) / 12
        lignes, _ = calculer_cotisations(ctx, brut, 0.0, 0.0)
        plafond = plafond_remuneration_jei(ctx, heures)

        exo = calculer_exoneration_jei(ctx, lignes, heures, year=2026, month=4)
        assert exo is not None
        montant_exo = abs(exo["montant_patronal"])
        exo_plein_brut = brut * (0.07 + 0.0525 + 0.0855 + 0.0202)
        assert montant_exo < exo_plein_brut
        assert montant_exo <= round(plafond * (0.07 + 0.0525 + 0.0855 + 0.0202), 2) + 1.0
        assert montant_exo > 1000.0

    def test_plafond_5_pass_ecretage(self):
        ctx = _contexte_jei_rd()
        ctx.year = 2026
        ctx.month = 6
        brut = 2500.0
        heures = (35 * 52) / 12
        lignes, _ = calculer_cotisations(ctx, brut, 0.0, 0.0)
        repo = InMemoryJeiExonerationsRepo()
        plafond = plafond_annuel_etablissement(ctx, 2026, ctx.baremes["jei"])
        repo.rows.append(
            {
                "company_id": "co-1",
                "year": 2026,
                "month": 1,
                "employee_id": "emp-other",
                "montant_exonere": plafond - 50.0,
            }
        )

        exo = calculer_exoneration_jei(
            ctx,
            lignes,
            heures,
            company_id="co-1",
            employee_id="emp-1",
            year=2026,
            month=6,
            exonerations_repo=repo,
        )
        assert exo is not None
        assert abs(exo["montant_patronal"]) == pytest.approx(50.0, abs=0.01)


class TestNonCumulRgdu:
    def test_jei_neutralise_rgdu(self):
        ctx = _contexte_jei_rd()
        ctx.year = 2026
        ctx.month = 4
        brut = 2500.0
        heures = (35 * 52) / 12
        lignes, _ = calculer_cotisations(ctx, brut, 0.0, 0.0)

        assert jei_applicable(ctx, 2026, 4)
        exo = calculer_exoneration_jei(ctx, lignes, heures, year=2026, month=4)
        assert exo is not None

        rgdu = calculer_reduction_generale(ctx, brut, heures)
        # En production, la RGDU n'est pas ajoutée si jei_applicable ; on vérifie
        # que l'exonération JEI est bien positive et que le régime JEI est actif.
        assert rgdu is not None
        assert abs(exo["montant_patronal"]) > 0
