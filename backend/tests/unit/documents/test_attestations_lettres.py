"""Les deux lettres remises à la demande du salarié (05/11/2026).

Attestation de travail : le « Modèle de lettre - Attestation d'emploi » du
ministère du Travail (https://code.travail.gouv.fr/modeles-de-courriers/attestation-de-travail,
mis à jour le 05/06/2023), plus la rémunération et la période d'essai que le
décret n° 2015-1437 demande pour un bailleur (service-public F1169 : « attestation
de l'employeur précisant l'emploi et la rémunération proposée, la date d'entrée en
fonctions envisagée et, si nécessaire, la durée de la période d'essai »).

Attestation de salaire : les mois préparés par la commande, depuis les bulletins remis.
Une donnée absente laisse des pointillés : rien n'est inventé.
"""
from __future__ import annotations

import io

import pytest
from PyPDF2 import PdfReader

from app.services.common_attestation_generator import (
    A_COMPLETER,
    CommonAttestationGenerator,
    anciennete,
)

pytestmark = pytest.mark.unit

SALARIEE = {
    "first_name": "Jeanne",
    "last_name": "Essai",
    "sexe": "F",
    "date_naissance": "1990-04-12",
    "lieu_naissance": "Lyon",
    "adresse": {"numero": "12", "rue": "rue des Lilas", "code_postal": "69003", "ville": "Lyon"},
    "job_title": "Opératrice de production",
    "contract_type": "CDD",
    "contract_end_date": "2026-12-31",
    "hire_date": "2025-08-01",
    "salaire_de_base": {"valeur": 2200, "type": "mensuel"},
}

SOCIETE = {
    "company_name": "Société Exemple",
    "siret": "12345678900011",
    "adresse_rue": "1 avenue de la Gare",
    "adresse_code_postal": "38000",
    "adresse_ville": "Grenoble",
    "nom_signataire_rh": "Paul Signataire",
    "qualite_signataire_rh": "Directeur des ressources humaines",
}

LE_5_NOVEMBRE = {"date_generation": "2026-11-05"}

TROIS_MOIS = [
    {"year": 2026, "month": 8, "brut": 2200.0, "net_avant_impot": 1720.4},
    {"year": 2026, "month": 9, "brut": 2350.5, "net_avant_impot": 1838.1},
    {"year": 2026, "month": 10, "brut": 2200.0, "net_avant_impot": 1720.4},
]


def _texte(pdf: bytes) -> str:
    assert pdf.startswith(b"%PDF")
    texte = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    return " ".join(texte.split())


def _travail(employee=SALARIEE, company=SOCIETE, **contexte) -> str:
    return _texte(
        CommonAttestationGenerator().generate(
            "attestation_emploi", employee, company, {**LE_5_NOVEMBRE, **contexte}
        )
    )


def _salaire(mois, employee=SALARIEE, nombre=3) -> str:
    return _texte(
        CommonAttestationGenerator().generate(
            "attestation_salaire",
            employee,
            SOCIETE,
            {**LE_5_NOVEMBRE, "mois_de_paie": mois, "nombre_mois_demande": nombre},
        )
    )


def test_deux_types_seulement():
    assert CommonAttestationGenerator.ATTESTATION_TYPES == [
        "attestation_emploi",
        "attestation_salaire",
    ]
    with pytest.raises(ValueError, match="non pris en charge"):
        CommonAttestationGenerator().generate("attestation_retraite", SALARIEE, SOCIETE, {})


def test_l_attestation_de_travail_suit_le_modele_du_ministere():
    texte = _travail()
    for attendu in (
        "Attestation de travail",
        "Paul Signataire, Directeur des ressources humaines, agissant pour le compte "
        "de la société Société Exemple",
        "1 avenue de la Gare, 38000 Grenoble",
        "SIRET 12345678900011",
        "Madame Jeanne Essai",
        "12 avril 1990 à Lyon",
        "12 rue des Lilas, 69003 Lyon",
        "Opératrice de production",
        "Contrat à durée déterminée (CDD) jusqu'au 31 décembre 2026",
        "1er août 2025",
        "1 an et 3 mois",
        "2 200,00 €",
        "fait toujours partie de nos effectifs à la date du 5 novembre 2026",
        "pour servir et valoir ce que de droit",
        "Fait à Grenoble, le 5 novembre 2026",
        "Signature et cachet de l'employeur",
    ):
        assert attendu in texte, attendu


def test_la_periode_d_essai_n_apparait_que_si_elle_est_en_cours():
    assert "Période d'essai" not in _travail()
    assert "Période d'essai en cours jusqu'au 1er décembre 2026" in _travail(
        periode_essai_fin="2026-12-01"
    )


def test_une_donnee_absente_laisse_des_pointilles():
    salarie = {k: v for k, v in SALARIEE.items() if k not in ("adresse", "sexe")}
    societe = {k: v for k, v in SOCIETE.items() if not k.endswith("_signataire_rh")}
    texte = _travail(employee=salarie, company=societe)
    assert f"Adresse {A_COMPLETER}" in texte
    assert f"Nom et fonction du signataire : {A_COMPLETER}" in texte
    assert "Madame" not in texte and "Monsieur" not in texte
    assert "Jeanne Essai fait toujours partie" in texte


def test_un_cdi_n_a_pas_de_terme():
    texte = _travail(employee={**SALARIEE, "contract_type": "CDI"})
    assert "Contrat à durée indéterminée (CDI)" in texte
    assert "jusqu'au 31 décembre 2026" not in texte


def test_l_attestation_de_salaire_reprend_les_bulletins():
    texte = _salaire(TROIS_MOIS)
    for attendu in (
        "Attestation de salaire",
        "Madame Jeanne Essai, qui occupe l'emploi « Opératrice de production » depuis le "
        "1er août 2025, a perçu les rémunérations suivantes au cours de ses 3 derniers mois de paie",
        "Net à payer avant impôt sur le revenu",
        "Août 2026 2 200,00 € 1 720,40 €",
        "Septembre 2026 2 350,50 € 1 838,10 €",
        "Total 6 750,50 € 5 278,90 €",
        "Montants repris de ses bulletins de paie",
        "Signature et cachet de l'employeur",
    ):
        assert attendu in texte, attendu


def test_un_seul_mois():
    texte = _salaire(TROIS_MOIS[-1:], nombre=3)
    assert "au cours de son dernier mois de paie" in texte


def test_un_net_inconnu_s_affiche_sans_etre_invente():
    texte = _salaire([{"year": 2026, "month": 10, "brut": 2200.0, "net_avant_impot": None}])
    assert "Octobre 2026 2 200,00 € —" in texte
    assert "Total 2 200,00 € —" in texte


def test_sans_mois_pas_de_lettre():
    with pytest.raises(ValueError, match="Aucun mois de paie"):
        _salaire([])


@pytest.mark.parametrize(
    "debut, jour, attendu",
    [
        ("2025-08-01", "2026-11-05", "1 an et 3 mois"),
        ("2026-10-20", "2026-11-05", "0 mois"),
        ("2023-11-05", "2026-11-05", "3 ans"),
        ("2024-01-31", "2026-11-05", "2 ans et 9 mois"),
    ],
)
def test_anciennete(debut, jour, attendu):
    from datetime import date

    assert anciennete(date.fromisoformat(debut), date.fromisoformat(jour)) == attendu
