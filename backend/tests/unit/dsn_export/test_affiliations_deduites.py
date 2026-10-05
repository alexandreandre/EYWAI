"""Affiliations prévoyance / santé (bloc 70) déduites des collègues.

Un salarié embauché après la reprise des DSN de l'ancien logiciel n'a pas
d'affiliations : DSN-VAL refuse alors ses bases 31 (CCH-11 / CCH-12 sur
S21.G00.78.005). On prend le jeu le plus fréquent chez ses collègues de la
même population (cadre / non-cadre) et dans la même situation face à la
mutuelle ce mois-là : un adhérent reçoit prévoyance et santé, un non-adhérent
la prévoyance seule.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.affiliations import Collegue, deduire_affiliations

pytestmark = pytest.mark.unit

PREVOYANCE_NC = {"id_contrat": "1", "option": "OPT1", "population": "02"}
PREVOYANCE_CADRE = {"id_contrat": "3", "option": "OPT1", "population": "01"}
SANTE = {"id_contrat": "2", "option": "ISO", "population": "00"}


def _affiliations(*contrats, depart=1):
    return [
        {**contrat, "id_affiliation": str(rang)}
        for rang, contrat in enumerate(contrats, start=depart)
    ]


COLLEGUES = [
    # Non-cadres adhérents : prévoyance + santé, dans un ordre ou dans l'autre.
    Collegue(cadre=False, adherent_mutuelle=True, affiliations=_affiliations(PREVOYANCE_NC, SANTE)),
    Collegue(cadre=False, adherent_mutuelle=True, affiliations=_affiliations(SANTE, PREVOYANCE_NC)),
    Collegue(
        cadre=False,
        adherent_mutuelle=True,
        affiliations=_affiliations(PREVOYANCE_NC, {**SANTE, "option": "FAM"}),
    ),
    # Non-cadre dispensé de mutuelle : la prévoyance seule.
    Collegue(cadre=False, adherent_mutuelle=False, affiliations=_affiliations(PREVOYANCE_NC)),
    # Cadre adhérent.
    Collegue(cadre=True, adherent_mutuelle=True, affiliations=_affiliations(SANTE, PREVOYANCE_CADRE)),
    # Sans affiliation : ne compte pas.
    Collegue(cadre=False, adherent_mutuelle=False, affiliations=[]),
]


def test_un_non_cadre_adherent_recoit_prevoyance_et_sante_les_plus_frequentes():
    deduites = deduire_affiliations(cadre=False, adherent_mutuelle=True, collegues=COLLEGUES)
    assert deduites == [
        {"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"},
        {"id_affiliation": "2", "id_contrat": "2", "option": "ISO", "population": "00"},
    ]


def test_un_non_cadre_non_adherent_ne_recoit_que_la_prevoyance():
    deduites = deduire_affiliations(cadre=False, adherent_mutuelle=False, collegues=COLLEGUES)
    assert deduites == [
        {"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"},
    ]


def test_un_cadre_recoit_le_jeu_des_cadres():
    deduites = deduire_affiliations(cadre=True, adherent_mutuelle=True, collegues=COLLEGUES)
    assert deduites == [
        {"id_affiliation": "1", "id_contrat": "2", "option": "ISO", "population": "00"},
        {"id_affiliation": "2", "id_contrat": "3", "option": "OPT1", "population": "01"},
    ]


def test_sans_modele_rien_n_est_deduit():
    # Aucun cadre dispensé de mutuelle chez les collègues.
    assert deduire_affiliations(cadre=True, adherent_mutuelle=False, collegues=COLLEGUES) == []
    assert deduire_affiliations(cadre=False, adherent_mutuelle=True, collegues=[]) == []


def test_seuls_les_champs_du_contrat_sont_copies():
    """L'identifiant technique (70.012) est celui du salarié, numéroté chez lui ;
    rien d'autre du collègue ne passe."""
    collegue = Collegue(
        cadre=False,
        adherent_mutuelle=False,
        affiliations=[{**PREVOYANCE_NC, "id_affiliation": "7", "date_debut": "2024-01-01"}],
    )
    deduites = deduire_affiliations(cadre=False, adherent_mutuelle=False, collegues=[collegue])
    assert deduites == [
        {"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"},
    ]


def test_a_egalite_le_choix_ne_depend_pas_de_l_ordre_des_collegues():
    a = Collegue(cadre=False, adherent_mutuelle=True, affiliations=_affiliations(PREVOYANCE_NC, SANTE))
    b = Collegue(
        cadre=False,
        adherent_mutuelle=True,
        affiliations=_affiliations(PREVOYANCE_NC, {**SANTE, "option": "FAM"}),
    )
    assert deduire_affiliations(
        cadre=False, adherent_mutuelle=True, collegues=[a, b]
    ) == deduire_affiliations(cadre=False, adherent_mutuelle=True, collegues=[b, a])


def test_une_option_absente_n_est_pas_inventee():
    sans_option = {"id_contrat": "1", "population": "NCADR5"}
    collegue = Collegue(
        cadre=False, adherent_mutuelle=False, affiliations=[{**sans_option, "id_affiliation": "1"}]
    )
    assert deduire_affiliations(cadre=False, adherent_mutuelle=False, collegues=[collegue]) == [
        {"id_affiliation": "1", "id_contrat": "1", "population": "NCADR5"},
    ]


SALARIE_FICTIF = {
    "id": "n1",
    "first_name": "Paul",
    "last_name": "FICTIF",
    "nir": "185017512345678",
    "sexe": "M",
    "date_naissance": "1985-01-15",
    "lieu_naissance": "LYON (69)",
    "adresse": {"rue": "1 rue Imaginaire", "ville": "LYON", "code_postal": "69001"},
    "hire_date": "2026-09-01",
    "contract_type": "CDI",
    "statut": "Non-Cadre",
    "duree_hebdomadaire": 35.0,
    "classification_conventionnelle": {"pcs": "674a", "idcc": "0292"},
}


def _construire(salarie):
    from app.modules.dsn_export.application.builder import build_individu_from_payroll

    return build_individu_from_payroll(
        salarie,
        {"salaire_brut": 2000.0, "synthese_net": {"net_imposable": 1600.0}},
        period="2026-10",
        company_siret="80248516900022",
    )


def test_le_builder_declare_les_affiliations_deduites_et_le_dit():
    deduites = [{"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"}]
    individu, avertissements = _construire(
        {**SALARIE_FICTIF, "affiliations_psc": deduites, "affiliations_psc_deduites": True}
    )
    assert individu.contrats[0].affiliations[0].rubriques["S21.G00.70.013"] == "1"
    assert any("déduites" in a and "1850175123456" in a for a in avertissements)


def test_des_affiliations_reprises_ne_declenchent_pas_l_avertissement():
    reprises = [{"id_affiliation": "1", "id_contrat": "1", "option": "OPT1", "population": "02"}]
    _, avertissements = _construire({**SALARIE_FICTIF, "affiliations_psc": reprises})
    assert not any("déduites" in a for a in avertissements)
