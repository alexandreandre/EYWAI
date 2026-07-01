"""Tests reconstruction cumuls."""

from pathlib import Path

from app.modules.dsn_import.application.cumuls import (
    _brut_from_versement,
    build_cumuls_for_month,
    build_cumuls_summary,
    extract_monthly_totals,
    plan_cumul_items,
)
from app.modules.dsn_import.domain.model import (
    CotisationBlock,
    CotisationIndividuelleBlock,
    RemunerationBlock,
    VersementBlock,
)
from app.modules.dsn_import.domain.parser import parse_dsn_files


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_monthly_totals():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    parsed = parse_dsn_files([("sample.txt", content)])
    ind = list(parsed.etablissements_by_siret().values())[0].individus[0]
    totals = extract_monthly_totals(ind)
    assert totals["brut"] == 3500.0
    assert totals["net_imposable"] == 2800.0
    assert totals["pas"] == 420.0


def test_build_cumuls_cumulative():
    prev = {"cumuls": {"brut_total": 1000.0, "net_imposable": 800.0}}
    month = {"brut": 500.0, "net_imposable": 400.0, "pas": 50.0, "heures": 151.67, "reduction_generale_patronale": 0.0}
    doc = build_cumuls_for_month(prev, month, 3)
    assert doc["cumuls"]["brut_total"] == 1500.0
    assert doc["periode"]["dernier_mois_calcule"] == 3


def test_plan_cumul_items():
    content = (FIXTURES / "sample_dsn_mars.txt").read_bytes()
    parsed = parse_dsn_files([("sample.txt", content)])
    items = plan_cumul_items(parsed)
    assert len(items) == 1
    assert items[0]["item_type"] == "cumul"


def test_build_cumuls_summary():
    items = [
        {
            "mapped_payload": {
                "period": "2026-01",
                "employee_key": "a",
                "month_totals": {"brut": 3000, "net_imposable": 2400, "pas": 300, "heures": 151.67},
            }
        },
        {
            "mapped_payload": {
                "period": "2026-01",
                "employee_key": "b",
                "month_totals": {"brut": 0, "net_imposable": 0, "pas": 0, "heures": 0},
            }
        },
    ]
    summary = build_cumuls_summary(items)
    assert summary["period_count"] == 1
    assert summary["employee_count"] == 2
    assert summary["entry_count"] == 2
    assert summary["by_period"][0]["brut"] == 3000.0
    assert summary["by_period"][0]["employees_without_brut"] == 1


def test_brut_from_remunerations_uses_max_primary_type():
    from app.modules.dsn_import.application.cumuls import _brut_from_remunerations
    from app.modules.dsn_import.domain.model import RemunerationBlock

    rems = [
        RemunerationBlock(type_code="001", montant=124.41),
        RemunerationBlock(type_code="003", montant=2174.18),
        RemunerationBlock(type_code="010", montant=2049.77),
    ]
    assert _brut_from_remunerations(rems) == 2174.18


def test_extract_monthly_totals_caps_net_above_brut():
    from app.modules.dsn_import.domain.model import (
        ContratBlock,
        IndividuBlock,
        RemunerationBlock,
        VersementBlock,
    )

    ver = VersementBlock(
        net_fiscal=4108.39,
        montant_soumis_pas=2111.41,
        remunerations=[RemunerationBlock(type_code="001", montant=2111.41)],
    )
    ind = IndividuBlock(contrats=[ContratBlock(versements=[ver])])
    totals = extract_monthly_totals(ind)
    assert totals["brut"] == 2111.41
    assert totals["net_imposable"] <= totals["brut"]


def test_brut_fallback_from_pas_assiette_when_primary_zero():
    ver = VersementBlock(
        montant_soumis_pas=1880.0,
        remunerations=[RemunerationBlock(type_code="001", montant=0.0)],
    )
    assert _brut_from_versement(ver) == 1880.0


def test_brut_fallback_not_used_without_zero_primary_line():
    ver = VersementBlock(montant_soumis_pas=1880.0, remunerations=[])
    assert _brut_from_versement(ver) == 0.0


def test_extract_monthly_totals_sums_cotisations():
    from app.modules.dsn_import.domain.model import ContratBlock, IndividuBlock

    ver = VersementBlock(
        net_fiscal=1950.0,
        remunerations=[RemunerationBlock(type_code="001", montant=2400.0)],
        cotisations=[
            CotisationBlock(montant_salarial=300.0, montant_patronal=450.0),
            CotisationBlock(montant_salarial=150.0, montant_patronal=200.0),
        ],
    )
    ind = IndividuBlock(contrats=[ContratBlock(versements=[ver])])
    totals = extract_monthly_totals(ind)
    assert totals["brut"] == 2400.0
    assert totals["employee_charges"] == 450.0
    assert totals["employer_charges"] == 650.0


def test_extract_monthly_totals_classifies_p26_individual_cotisations():
    from app.modules.dsn_import.domain.model import ContratBlock, IndividuBlock

    ver = VersementBlock(
        net_fiscal=1950.0,
        remunerations=[RemunerationBlock(type_code="001", montant=2400.0)],
        cotisations_individuelles=[
            CotisationIndividuelleBlock(code="045", montant_patronal=70.0),
            CotisationIndividuelleBlock(code="072", montant_patronal=180.0),
            CotisationIndividuelleBlock(code="018", montant_patronal=25.0),
            CotisationIndividuelleBlock(code="999", montant_patronal=12.0),
        ],
    )
    ind = IndividuBlock(contrats=[ContratBlock(versements=[ver])])

    totals = extract_monthly_totals(ind)

    assert totals["employer_charges"] == 45.0
    assert totals["employer_charges_source"] == "dsn_classified"
    detail = totals["dsn_cotisations_detail"]
    assert detail["employer_codes"] == {"045": 70.0}
    assert detail["reduction_codes"] == {"018": -25.0}
    assert detail["ignored_codes"] == {"072": 180.0}
    assert detail["unknown_codes"] == {"999": 12.0}
