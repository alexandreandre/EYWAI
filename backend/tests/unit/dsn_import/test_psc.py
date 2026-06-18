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
