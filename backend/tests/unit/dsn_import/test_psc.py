"""Tests extraction PSC mutuelle / prévoyance depuis DSN."""

from app.modules.dsn_import.domain.model import (
    AffiliationBlock,
    ContratBlock,
    CotisationBlock,
    CotisationIndividuelleBlock,
    VersementBlock,
)
from app.modules.dsn_import.domain.psc import (
    build_specificites_paie_psc,
    extract_psc_from_contrat,
    infer_pack_from_code_option,
)


def test_infer_pack_isole_famille():
    assert infer_pack_from_code_option("ISO") == "isole"
    assert infer_pack_from_code_option("FAM") == "famille"
    assert infer_pack_from_code_option("FAMILLE") == "famille"
    assert infer_pack_from_code_option("", nb_enfants=2) == "famille"


def test_extract_mutuelle_from_affiliation_and_cotisation():
    contrat = ContratBlock(
        statut="04",
        affiliations=[
            AffiliationBlock(
                reference_contrat="REF001",
                code_organisme="123456789",
                code_option="FAM",
                code_population="01",
            )
        ],
        versements=[
            VersementBlock(
                cotisations_individuelles=[
                    CotisationIndividuelleBlock(
                        code="059",
                        montant_assiette=0,
                        montant_salarial=78.0,
                        montant_patronal=45.0,
                    )
                ]
            )
        ],
    )
    psc = extract_psc_from_contrat(contrat)
    assert psc.mutuelle_adhesion is True
    assert psc.pack_couverture == "famille"
    assert psc.mutuelle_amounts is not None
    assert psc.mutuelle_amounts.montant_salarial == 78.0


def test_build_specificites_paie_psc_cadre_prevoyance():
    contrat = ContratBlock(
        statut="04",
        affiliations=[
            AffiliationBlock(code_organisme="P1234", code_option="ISO")
        ],
        versements=[
            VersementBlock(
                cotisations=[
                    CotisationBlock(
                        code="059",
                        base=3000.0,
                        montant_salarial=45.0,
                        montant_patronal=45.0,
                    )
                ]
            )
        ],
    )
    spec = build_specificites_paie_psc(contrat)
    assert spec["mutuelle"]["adhesion"] is False
    assert spec["prevoyance"]["adhesion"] is True
    assert spec["_psc_meta"]["statut_categoriel"] == "cadre"
    assert spec["prevoyance"]["lignes_specifiques"]


def test_parse_dsn_psc_fixture_end_to_end():
    from pathlib import Path

    from app.modules.dsn_import.application.mapping import map_employee_payload
    from app.modules.dsn_import.domain.parser import parse_dsn_content

    content = (Path(__file__).parent / "fixtures" / "sample_dsn_psc.txt").read_bytes()
    dsn = parse_dsn_content(content, file_name="sample_dsn_psc.txt")
    ind = dsn.etablissement.individus[0]
    contrat = ind.contrats[0]
    assert len(contrat.affiliations) == 1
    assert contrat.affiliations[0].code_option == "FAM"
    assert contrat.versements[0].cotisations_individuelles[0].montant_salarial == 78.0

    payload = map_employee_payload(ind, dsn.etablissement, dsn.etablissement.siret)
    mutuelle = payload["specificites_paie"]["mutuelle"]
    assert mutuelle["adhesion"] is True
    assert mutuelle["pack_couverture"] == "famille"
    assert mutuelle["lignes_specifiques"][0]["montant_salarial"] == 78.0


def test_parse_dsn_psc_cegid_dual_affiliation():
    from pathlib import Path

    from app.modules.dsn_import.application.mapping import map_employee_payload
    from app.modules.dsn_import.domain.parser import parse_dsn_content

    content = (Path(__file__).parent / "fixtures" / "sample_dsn_psc_cegid.txt").read_bytes()
    dsn = parse_dsn_content(content, file_name="sample_dsn_psc_cegid.txt")
    etab = dsn.etablissement

    assert len(etab.organismes_psc) == 2
    assert etab.organismes_psc[0].reference_contrat == "E00000601206899"
    assert etab.organismes_psc[1].reference_contrat == "PI51044PE000"

    ind = etab.individus[0]
    contrat = ind.contrats[0]
    assert len(contrat.affiliations) == 2
    assert contrat.affiliations[0].code_population == "841"
    assert contrat.affiliations[1].code_population == "ENSP"

    c059 = [ci for v in contrat.versements for ci in v.cotisations_individuelles if ci.code == "059"]
    assert len(c059) == 2
    assert c059[0].montant_salarial == 78.0
    assert c059[0].montant_patronal == 0.0
    assert c059[1].montant_salarial == 45.0

    payload = map_employee_payload(ind, etab, etab.siret)
    mutuelle = payload["specificites_paie"]["mutuelle"]
    prevoyance = payload["specificites_paie"]["prevoyance"]

    assert mutuelle["adhesion"] is True
    assert mutuelle["lignes_specifiques"][0]["montant_salarial"] == 78.0
    assert prevoyance["adhesion"] is True
    assert prevoyance["lignes_specifiques"]
    assert prevoyance["lignes_specifiques"][0]["patronal"] > 0

