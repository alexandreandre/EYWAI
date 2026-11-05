"""Le référentiel PCS-ESE : la table DSN PCSESE P26V01 et les métiers des pages Insee."""

from app.modules.pcs_ese.domain.referentiel import CODES_ECAP, charger_referentiel, code_valide


def test_430_codes_dont_9999():
    ref = charger_referentiel()
    assert len(ref) == 430
    assert "9999" in ref
    assert ref["9999"].typiques == ()


def test_metiers_insee_lus():
    r = charger_referentiel()["543g"]
    assert r.libelle == "Employés administratifs qualifiés des autres services des entreprises"
    assert (
        "Employé de bureau (sauf Etat, coll. loc., banque, assurances, transports), employé qualifié"
        in r.typiques
    )
    assert any(e.voir == ("524b",) for e in r.exclues)
    assert r.groupe == "5"


def test_codes_publics_et_ecap():
    ref = charger_referentiel()
    assert sum(r.public for r in ref.values()) == 17
    assert ref["624d"].ecap and ref["643a"].ecap
    assert not ref["674a"].ecap
    assert len(CODES_ECAP) == 36
    assert CODES_ECAP <= set(ref)


def test_code_valide_casse_comprise():
    assert code_valide("674a")
    assert code_valide("9999")
    assert not code_valide("674A")
    assert not code_valide("999a")
    assert not code_valide("")
