"""Tests unitaires — bulletin de régularisation participation (salarié parti).

Vérifie le régime social/fiscal : participation exonérée de cotisations,
soumise à CSG/CRDS 9,7 %, net numéraire = brut − CSG.
"""

from __future__ import annotations

from app.modules.participation.domain.bulletin_rules import compute_participation_csg
from app.modules.participation.domain.regularisation_payslip import (
    REGULARISATION_KIND,
    build_regularisation_participation_payslip_data,
)


def _bulletin(gross: float, cash: float, pee: float, advance: float = 0.0) -> dict:
    non_ded, ded, _ = compute_participation_csg(gross)
    return {
        "id": "b-1",
        "campaign_id": "c-1",
        "employee_id": "e-1",
        "dispositif_type": "participation",
        "gross_amount": gross,
        "csg_non_deductible": float(non_ded),
        "csg_deductible": float(ded),
        "advance_amount": advance,
        "advance_label": "Acompte" if advance else "",
        "net_amount": gross - float(non_ded) - float(ded) - advance,
        "choice_type": "partial_cash",
        "choice_cash_amount": cash,
        "pee_amount": pee,
    }


_EMP = {"first_name": "Jean", "last_name": "Parti", "nir": "1234567890123", "job_title": "Opérateur"}
_COMP = {"raison_sociale": "ACME", "siret": "12345678900011"}


class TestBuildRegularisationPayslip:
    def test_marker_and_period(self):
        data = build_regularisation_participation_payslip_data(
            bulletin=_bulletin(1000, 1000, 0),
            employee=_EMP,
            company=_COMP,
            year=2027,
            month=5,
            exercise_label="PARTICIPATION 2026",
        )
        assert data["bulletin_kind"] == REGULARISATION_KIND
        assert data["is_regularisation"] is True
        assert data["en_tete"]["periode"] == "Mai 2027"

    def test_no_social_contributions_only_csg(self):
        """Aucune cotisation classique : seules 2 lignes CSG/CRDS."""
        data = build_regularisation_participation_payslip_data(
            bulletin=_bulletin(3225.33, 2912.48, 0),
            employee=_EMP,
            company=_COMP,
            year=2027,
            month=5,
        )
        cotis = data["structure_cotisations"]["cotisations"]
        assert len(cotis) == 2
        libelles = {c["libelle"] for c in cotis}
        assert any("CSG déductible" in lbl for lbl in libelles)
        assert any("non déductible" in lbl for lbl in libelles)
        # CSG totale 9,7 % de 3225.33 = 312.85
        assert data["structure_cotisations"]["total_salarial"] == 312.85
        assert data["structure_cotisations"]["total_patronal"] == 0.0

    def test_net_cash_equals_gross_minus_csg(self):
        non_ded, ded, _ = compute_participation_csg(3225.33)
        cash_net = round(3225.33 - float(non_ded) - float(ded), 2)
        data = build_regularisation_participation_payslip_data(
            bulletin=_bulletin(3225.33, cash_net, 0),
            employee=_EMP,
            company=_COMP,
            year=2027,
            month=5,
        )
        assert data["salaire_brut"] == 3225.33
        assert data["net_a_payer"] == cash_net
        # Numéraire imposable IR ; pas de PAS prélevé à la source.
        assert data["synthese_net"]["net_imposable"] == cash_net
        assert data["synthese_net"]["impot_preleve_a_la_source"] == 0.0

    def test_pee_part_not_paid_but_present(self):
        """Part PEE affichée mais non versée (net = numéraire seul)."""
        data = build_regularisation_participation_payslip_data(
            bulletin=_bulletin(2000, 0, 1806),  # tout en PEE
            employee=_EMP,
            company=_COMP,
            year=2027,
            month=5,
        )
        assert data["regularisation"]["part_pee"] == 1806.0
        assert data["net_a_payer"] == 0.0

    def test_dsn_compatible_brut_positive(self):
        """Le brut doit être > 0 pour passer le contrôle DSN (brut <= 0 bloquant)."""
        data = build_regularisation_participation_payslip_data(
            bulletin=_bulletin(1500, 1354.5, 0),
            employee=_EMP,
            company=_COMP,
            year=2027,
            month=5,
        )
        assert data["salaire_brut"] > 0
        assert data["synthese_net"]["net_imposable"] <= data["salaire_brut"]
