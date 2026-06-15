"""Tests parser norme DSN moderne (NIC + rubriques individu P22+)."""

from pathlib import Path

from app.modules.dsn_import.application.mapping import build_preview_items
from app.modules.dsn_import.domain.parser import parse_dsn_content, parse_dsn_files
from app.modules.dsn_import.domain.validation import validate_parsed_dsn

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_modern_dsn_nic_and_individu():
    content = (FIXTURES / "sample_dsn_modern.txt").read_bytes()
    dsn = parse_dsn_content(content, file_name="sample_dsn_modern.txt")

    assert dsn.entreprise.siren == "951474782"
    assert dsn.etablissement.nic == "00020"
    assert dsn.etablissement.siret == "95147478200020"
    assert dsn.declaration.mois_principal == "01062025"
    assert dsn.entreprise.nic_siege == "00001"

    ind = dsn.etablissement.individus[0]
    assert ind.nom == "BERTAUD"
    assert ind.prenom == "Jean"
    assert ind.nir == "180032710123448"
    assert ind.matricule == "1970879049270"

    parsed = parse_dsn_files([("sample_dsn_modern.txt", content)])
    assert parsed.siren == "951474782"
    etabs = parsed.etablissements_by_siret()
    assert "95147478200020" in etabs

    anomalies = validate_parsed_dsn(parsed)
    blocking = [a for a in anomalies if a.get("severity") == "blocking"]
    assert not blocking

    items, summary = build_preview_items(parsed)
    assert summary["employee_count"] == 1
    assert summary["period_min"] == "2025-06"
    group = next(i for i in items if i["item_type"] == "group")
    assert group["mapped_payload"]["group_name"] == "Groupe 951474782"
    etab = next(i for i in items if i["item_type"] == "establishment")
    assert "NIORT" in etab["mapped_payload"]["company_name"]

    emp = next(i for i in items if i["item_type"] == "employee")
    assert emp["mapped_payload"]["salaire_de_base"]["valeur"] == 2200.0
    assert emp.get("needs_review") is False

    from app.modules.dsn_import.application.cumuls import build_cumuls_summary, plan_cumul_items

    cumuls = plan_cumul_items(parsed)
    cs = build_cumuls_summary(cumuls)
    assert cs["totals"]["brut"] == 2200.0
    assert cs["totals"]["net_imposable"] == 1760.0
    assert cs["totals"]["pas"] == 42.0
    assert cs["totals"]["heures"] == 151.67
    assert cs["by_period"][0]["employees_without_brut"] == 0


def test_brut_does_not_sum_required_remuneration_types():
    """Les types 001/002/003/010 sont des vues du même salaire — on ne les additionne pas."""
    content = (FIXTURES / "sample_dsn_modern.txt").read_text(encoding="utf-8")
    extra = (
        "\nS21.G00.51.001,'01062025'\n"
        "S21.G00.51.002,'30062025'\n"
        "S21.G00.51.011,'002'\n"
        "S21.G00.51.013,'2200.00'\n"
        "S21.G00.51.001,'01062025'\n"
        "S21.G00.51.002,'30062025'\n"
        "S21.G00.51.011,'003'\n"
        "S21.G00.51.013,'2200.00'\n"
        "S21.G00.51.001,'01062025'\n"
        "S21.G00.51.002,'30062025'\n"
        "S21.G00.51.011,'010'\n"
        "S21.G00.51.013,'1800.00'\n"
    )
    parsed = parse_dsn_files([("multi_rem.txt", content.encode() + extra.encode())])
    from app.modules.dsn_import.application.cumuls import build_cumuls_summary, plan_cumul_items

    cs = build_cumuls_summary(plan_cumul_items(parsed))
    assert cs["totals"]["brut"] == 2200.0


def test_heures_from_activite_when_rem_heures_absent():
    """Comme CARTOL P26 : activité 151,67 sans unité, jours calendaires 40 ignorés."""
    content = (FIXTURES / "sample_dsn_modern.txt").read_text(encoding="utf-8")
    # Retire .012 sur rémunération pour forcer le repli activité
    content = content.replace("S21.G00.51.012,'151.67'\n", "")
    extra = (
        "\nS21.G00.53.001,'01'\n"
        "S21.G00.53.002,'31.00'\n"
        "S21.G00.53.003,'40'\n"
        "S21.G00.53.001,'01'\n"
        "S21.G00.53.002,'151.67'\n"
    )
    parsed = parse_dsn_files([("act.txt", content.encode() + extra.encode())])
    from app.modules.dsn_import.application.cumuls import build_cumuls_summary, plan_cumul_items

    cs = build_cumuls_summary(plan_cumul_items(parsed))
    assert cs["totals"]["heures"] == 151.67
