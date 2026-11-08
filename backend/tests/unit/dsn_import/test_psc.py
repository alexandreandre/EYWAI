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

    # Corrigé le 08/11 : ce test posait « 841 » = mutuelle et « ENSP » = prévoyance, l'inverse de la
    # DSN réelle de Cartol. L'affiliation ENSP renvoie (70.013 = 2) à l'adhésion 779558501, une
    # mutuelle (code sur 9 chiffres) ; l'affiliation 841 renvoie à une adhésion absente du fichier et
    # rien d'autre ne dit son contrat : aucune prévoyance n'est déduite de l'ordre des cotisations.
    assert mutuelle["adhesion"] is True
    assert mutuelle["lignes_specifiques"][0]["montant_salarial"] == 78.0
    assert (mutuelle.get("dsn") or {}).get("code_organisme") == "779558501"
    assert prevoyance["adhesion"] is False



# --- Adhésions liées (Cartol, DSN de septembre 2026 ; défaut corrigé le 08/11) ------------------


def _dsn_liee():
    from pathlib import Path

    from app.modules.dsn_import.domain.parser import parse_dsn_content

    content = (Path(__file__).parent / "fixtures" / "sample_dsn_psc_adhesions_liees.txt").read_bytes()
    return parse_dsn_content(content, file_name="sample_dsn_psc_adhesions_liees.txt")


def test_le_lien_affiliation_adhesion_et_cotisation_est_lu():
    """70.013 renvoie au 15.005 de l'adhésion ; 78.005 (base 31) renvoie au 70.012 de l'affiliation,
    et la cotisation 059 qui suit porte ce lien."""
    contrat = _dsn_liee().etablissement.individus[0].contrats[0]
    assert [(a.identifiant_affiliation, a.identifiant_adhesion) for a in contrat.affiliations] == [("2", "1"), ("1", "2")]
    c059 = [ci for v in contrat.versements for ci in v.cotisations_individuelles if ci.code == "059"]
    assert [(ci.identifiant_affiliation, ci.montant_salarial) for ci in c059] == [("1", 59.27), ("2", 57.22)]


def test_la_prevoyance_d_un_salarie_sans_mutuelle_n_est_pas_prise_pour_une_mutuelle():
    """Cartol, sept. 2026 : une seule affiliation, au contrat Groupama (prévoyance, base « Tranche A
    Prévoyance » 79.001 = 11), population « 841 ». L'import posait sa cotisation de prévoyance
    (46,14 = 1,18 % + 1,18 %) comme mutuelle."""
    from app.modules.dsn_import.application.mapping import map_employee_payload

    dsn = _dsn_liee()
    payload = map_employee_payload(dsn.etablissement.individus[1], dsn.etablissement, dsn.etablissement.siret)
    spec = payload["specificites_paie"]
    assert spec["mutuelle"]["adhesion"] is False
    assert not spec["mutuelle"].get("lignes_specifiques")
    assert spec["prevoyance"]["adhesion"] is True


def test_mutuelle_et_prevoyance_suivent_leur_affiliation_et_non_l_ordre_ni_la_population():
    """Population « ENSP » sur la mutuelle (forfait, 79.001 = 20) et « 841 » sur la prévoyance :
    c'est l'inverse des listes fixes de codes population."""
    from app.modules.dsn_import.application.mapping import map_employee_payload

    dsn = _dsn_liee()
    spec = map_employee_payload(dsn.etablissement.individus[0], dsn.etablissement, dsn.etablissement.siret)["specificites_paie"]
    assert spec["mutuelle"]["adhesion"] is True
    assert spec["mutuelle"]["lignes_specifiques"][0]["montant_salarial"] == 59.27
    assert spec["prevoyance"]["adhesion"] is True
    assert (spec["mutuelle"].get("dsn") or {}).get("code_organisme") == "779558501"


def test_une_base_forfaitaire_de_la_taille_du_salaire_est_une_prevoyance():
    """Colorplast et Comitech (Cegid Quadra) déclarent leur prévoyance non cadre en « Base forfaitaire
    Prévoyance » (79.001 = 18) d'un montant égal au brut ; la santé, elle, en 18 à 29,24 et 20 à
    98,12. Un composant forfaitaire de l'ordre du salaire est une prévoyance."""
    from app.modules.dsn_import.domain.model import ComposantBaseBlock
    from app.modules.dsn_import.domain.psc import _affiliation_kind

    contrat = ContratBlock(
        affiliations=[AffiliationBlock(identifiant_affiliation="1"), AffiliationBlock(identifiant_affiliation="2")],
        versements=[VersementBlock(composants_base=[
            ComposantBaseBlock(code="18", montant=29.24, identifiant_affiliation="1"),
            ComposantBaseBlock(code="18", montant=2543.39, identifiant_affiliation="2"),
        ])],
    )
    assert _affiliation_kind(contrat.affiliations[0], contrat) == "mutuelle"
    assert _affiliation_kind(contrat.affiliations[1], contrat) == "prevoyance"


def test_une_sante_au_pourcentage_du_plafond_reste_une_mutuelle():
    """Mont Blanc (18) et Zone 404 (11) déclarent leur santé sur 4 005,00, le plafond, quel que soit le
    salaire ; la prévoyance sur le brut, avec une tranche B au-delà du plafond."""
    from app.modules.dsn_import.domain.model import ComposantBaseBlock, RemunerationBlock
    from app.modules.dsn_import.domain.psc import _affiliation_kind

    def contrat(brut, *composants):
        return ContratBlock(
            affiliations=[AffiliationBlock(identifiant_affiliation="1"), AffiliationBlock(identifiant_affiliation="2")],
            versements=[VersementBlock(
                remunerations=[RemunerationBlock(type_code="001", montant=brut)],
                composants_base=[ComposantBaseBlock(code=c, montant=m, identifiant_affiliation=a) for a, c, m in composants])],
        )

    c = contrat(3608.0, ("1", "11", 4005.0), ("2", "11", 3608.0))
    assert [_affiliation_kind(a, c) for a in c.affiliations] == ["mutuelle", "prevoyance"]
    c = contrat(5000.0, ("1", "11", 4005.0), ("2", "11", 4005.0), ("2", "13", 995.0))
    assert [_affiliation_kind(a, c) for a in c.affiliations] == ["mutuelle", "prevoyance"]
    c = contrat(2182.77, ("1", "18", 4005.0), ("2", "11", 2163.10))
    assert [_affiliation_kind(a, c) for a in c.affiliations] == ["mutuelle", "prevoyance"]


def test_le_plafond_l_emporte_quand_le_brut_en_est_proche():
    """Mont Blanc : santé en 18 à 4 005,00 pour un brut de 3 984,00."""
    from app.modules.dsn_import.domain.model import ComposantBaseBlock, RemunerationBlock
    from app.modules.dsn_import.domain.psc import _affiliation_kind

    c = ContratBlock(
        affiliations=[AffiliationBlock(identifiant_affiliation="1"), AffiliationBlock(identifiant_affiliation="2")],
        versements=[VersementBlock(
            remunerations=[RemunerationBlock(type_code="001", montant=3984.0)],
            composants_base=[ComposantBaseBlock(code="18", montant=4005.0, identifiant_affiliation="1"),
                             ComposantBaseBlock(code="11", montant=3984.0, identifiant_affiliation="2")])],
    )
    assert [_affiliation_kind(a, c) for a in c.affiliations] == ["mutuelle", "prevoyance"]
