"""Les deux lettres remises à la demande du salarié.

Attestation d'emploi (07/11/2026) : le modèle envoyé par la cliente le 06/11/2026
(« Attestation_emploi », société LEWIS), rien de plus. Cinq lignes dans cet ordre
(nom et prénom, n° de sécurité sociale, adresse, emploi occupé, reprise
d'ancienneté), la phrase de présence, la formule finale, le lieu et la date, le
signataire, la mention du pied de page. Une donnée absente de la fiche est dite
en toutes lettres : jamais inventée, jamais laissée vide.

Attestation de salaire : les mois préparés par la commande, depuis les bulletins remis.
"""
from __future__ import annotations

import io

import pytest
from PyPDF2 import PdfReader

from app.services.common_attestation_generator import (
    A_COMPLETER,
    CommonAttestationGenerator,
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
    "nir": "290046912345678",
    "seniority_reference_date": "2015-08-01",
}

SOCIETE = {
    "company_name": "Société Exemple",
    "siret": "12345678900011",
    "code_naf": "2550B",
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


def _dans_l_ordre(texte: str, morceaux) -> None:
    position = 0
    for morceau in morceaux:
        trouve = texte.find(morceau, position)
        assert trouve >= 0, f"absent ou hors d'ordre : {morceau!r}"
        position = trouve + len(morceau)


def test_l_attestation_d_emploi_suit_le_modele_de_la_cliente():
    texte = _travail()
    _dans_l_ordre(
        texte,
        (
            "1 avenue de la Gare, 38000 Grenoble",
            "SIRET : 123 456 789 00011",
            "Code NAF : 2550B",
            "ATTESTATION D'EMPLOI",
            "Nous soussignés, la société Société Exemple, certifions que :",
            "Nom et prénom Mme Jeanne ESSAI",
            "N° de sécurité sociale 2 90 04 69 123 456 78",
            "Adresse 12 rue des Lilas, 69003 Lyon",
            "Emploi occupé Opératrice de production",
            "Reprise d'ancienneté 01/08/2015",
            "est employée au sein de notre entreprise depuis le 01/08/2025 et fait toujours "
            "partie de nos effectifs à la date de la présente attestation.",
            "Cette attestation est délivrée à l'intéressée pour servir et valoir ce que de droit.",
            "Fait à Grenoble, le 05/11/2026",
            "Nom, qualité et signature de l'employeur",
            "Paul Signataire",
            "Directeur des ressources humaines",
        ),
    )
    # Le pied du modèle cite L1221-10, qui porte sur la DPAE : Martine ne le recopie pas.
    assert "L1221-10" not in texte


def test_cinq_lignes_et_rien_d_autre():
    """Le tableau du modèle : cinq lignes, exactement. La fiche en dit plus, la lettre non."""
    texte = _travail()
    tableau = texte.split("certifions que :", 1)[1].split(" est employée", 1)[0].strip()
    assert tableau == (
        "Nom et prénom Mme Jeanne ESSAI "
        "N° de sécurité sociale 2 90 04 69 123 456 78 "
        "Adresse 12 rue des Lilas, 69003 Lyon "
        "Emploi occupé Opératrice de production "
        "Reprise d'ancienneté 01/08/2015"
    )
    for absent in (
        "naissance", "1990", "Nature du contrat", "CDD", "Date d'entrée", "Temps de travail",
        "Rémunération", "2 200", "Période d'essai", "Départ prévu", "Attestation de travail",
    ):
        assert absent not in texte, absent


def test_la_lettre_d_emploi_ignore_l_essai_et_le_depart():
    texte = _travail(periode_essai_fin="2026-12-01", depart_prevu="2026-11-30")
    for absent in ("Période d'essai", "période d'essai", "01/12/2026", "Départ", "30/11/2026"):
        assert absent not in texte, absent


def test_un_nir_absent_est_dit():
    texte = _travail(employee={**SALARIEE, "nir": None})
    assert "N° de sécurité sociale Non renseigné sur la fiche salarié Adresse" in texte


def test_une_reprise_d_anciennete_absente_est_dite():
    texte = _travail(employee={**SALARIEE, "seniority_reference_date": None})
    assert "Reprise d'ancienneté Non renseignée sur la fiche salarié" in texte


def test_la_date_d_anciennete_de_la_dsn_sert_a_defaut():
    specificites = {"dsn_anciennete": {"date_anciennete": "2020-08-01"}}
    salarie = {**SALARIEE, "seniority_reference_date": None, "specificites_paie": specificites}
    assert "Reprise d'ancienneté 01/08/2020" in _travail(employee=salarie)


def test_chaque_ligne_absente_est_dite():
    salarie = {**SALARIEE, "adresse": None, "job_title": "", "first_name": None, "last_name": None}
    texte = _travail(employee=salarie)
    assert "Nom et prénom Non renseigné sur la fiche salarié" in texte
    assert "Adresse Non renseignée sur la fiche salarié" in texte
    assert "Emploi occupé Non renseigné sur la fiche salarié" in texte


def test_une_date_d_entree_absente_est_dite():
    texte = _travail(employee={**SALARIEE, "hire_date": None})
    assert (
        "est employée au sein de notre entreprise depuis le (date d'entrée non renseignée "
        "sur la fiche salarié) et fait toujours partie" in texte
    )


def test_un_nir_deja_espace_est_regroupe_comme_le_modele():
    texte = _travail(employee={**SALARIEE, "nir": "2 90 04 69 123 456 78"})
    assert "N° de sécurité sociale 2 90 04 69 123 456 78" in texte


def test_un_salarie_au_masculin():
    texte = _travail(employee={**SALARIEE, "sexe": "M", "first_name": "Paul"})
    assert "Nom et prénom M. Paul ESSAI" in texte
    assert "est employé au sein de notre entreprise" in texte
    assert "délivrée à l'intéressé pour servir" in texte


def test_sans_sexe_sur_la_fiche_la_phrase_reste_neutre():
    texte = _travail(employee={**SALARIEE, "sexe": None})
    assert "Nom et prénom Jeanne ESSAI" in texte
    assert "travaille au sein de notre entreprise depuis le 01/08/2025" in texte
    assert "délivrée à la personne intéressée pour servir" in texte
    assert "Mme" not in texte and "M." not in texte


def test_une_embauche_a_venir_n_est_pas_encore_dans_les_effectifs():
    texte = _travail(employee={**SALARIEE, "hire_date": "2026-12-01"})
    assert "sera employée au sein de notre entreprise à compter du 01/12/2026." in texte
    assert "fait toujours partie" not in texte


def test_sans_signataire_la_place_reste_a_remplir():
    societe = {k: v for k, v in SOCIETE.items() if not k.endswith("_signataire_rh")}
    texte = _travail(company=societe)
    assert f"Nom, qualité et signature de l'employeur {A_COMPLETER}" in texte


def test_une_societe_sans_naf_le_dit():
    societe = {k: v for k, v in SOCIETE.items() if k != "code_naf"}
    assert "Code NAF : non renseigné" in _travail(company=societe)


def test_le_code_naf_de_la_fiche_entreprise():
    societe = {**{k: v for k, v in SOCIETE.items() if k != "code_naf"}, "naf_ape": "2550B"}
    assert "Code NAF : 2550B" in _travail(company=societe)


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


def test_une_rue_saisie_avec_son_numero_en_double():
    """Une fiche du test au 05/11 : le champ rue lui-même porte le numéro deux fois."""
    from app.services.common_attestation_generator import adresse_du_salarie

    adresse = {"numero": "12", "rue": "12 12 rue des Lilas", "code_postal": "69003", "ville": "Lyon"}
    assert adresse_du_salarie({"adresse": adresse}) == "12 rue des Lilas, 69003 Lyon"
    assert adresse_du_salarie({"adresse": {"rue": "12 12 rue des Lilas"}}) == "12 rue des Lilas"


def test_le_numero_deja_dans_la_rue_n_est_pas_repete():
    """Sur le test (05/11), les 271 adresses qui ont un numéro le portent aussi dans la rue."""
    from app.services.common_attestation_generator import adresse_du_salarie

    adresse = {"numero": "10", "rue": "10 rue des Lilas", "code_postal": "69003", "ville": "Lyon"}
    assert adresse_du_salarie({"adresse": adresse}) == "10 rue des Lilas, 69003 Lyon"
    assert adresse_du_salarie({"adresse": {**adresse, "rue": "rue des Lilas"}}) == "10 rue des Lilas, 69003 Lyon"
    assert adresse_du_salarie({"adresse": {**adresse, "numero": "1", "rue": "10 rue des Lilas"}}) == (
        "1 10 rue des Lilas, 69003 Lyon"
    )


def _salaire_contexte(**contexte) -> str:
    return _texte(
        CommonAttestationGenerator().generate(
            "attestation_salaire",
            SALARIEE,
            SOCIETE,
            {**LE_5_NOVEMBRE, "mois_de_paie": TROIS_MOIS, "nombre_mois_demande": 3, **contexte},
        )
    )


def test_un_salarie_parti_n_occupe_plus_l_emploi():
    texte = _salaire_contexte(a_quitte=True, date_de_sortie="2026-10-31")
    assert (
        "qui a occupé l'emploi « Opératrice de production » du 1er août 2025 au 31 octobre 2026, a perçu"
        in texte
    )
    assert "qui occupe" not in texte


def test_un_salarie_parti_sans_date_de_sortie():
    texte = _salaire_contexte(a_quitte=True, date_de_sortie=None)
    assert "qui a occupé l'emploi « Opératrice de production » à partir du 1er août 2025, a perçu" in texte


# --- La lettre passe par le vrai service, sans repli silencieux ------------------


@pytest.fixture
def service_sans_modele(monkeypatch):
    from app.services import document_service as module

    monkeypatch.setattr(module.document_service, "get_active_template", lambda *_: None)
    return module


def test_la_lettre_de_salaire_traverse_le_service(service_sans_modele):
    import json

    contexte = {**LE_5_NOVEMBRE, "mois_de_paie": TROIS_MOIS, "nombre_mois_demande": 3, "a_quitte": False}
    resultat = service_sans_modele.document_service.generate_document(
        company_id="soc-1",
        employee_id="sal-1",
        document_type="attestation_salaire",
        category="attestation_courante",
        employee_data=SALARIEE,
        company_data=SOCIETE,
        context=contexte,
        persist=False,
    )
    assert "Total 6 750,50 € 5 278,90 €" in _texte(resultat["pdf_bytes"])
    json.dumps(contexte)  # generation_context part en JSONB


def test_une_lettre_qui_plante_ne_sort_pas_en_version_de_repli(service_sans_modele, monkeypatch):
    def _plante(*_a, **_k):
        raise RuntimeError("panne du générateur")

    monkeypatch.setattr(service_sans_modele.common_attestation_generator, "generate", _plante)
    monkeypatch.setattr(
        service_sans_modele.document_service,
        "_generate_fallback_pdf",
        lambda *_: pytest.fail("une attestation ne doit jamais sortir en lettre de repli"),
    )
    with pytest.raises(RuntimeError, match="panne du générateur"):
        service_sans_modele.document_service.generate_document(
            company_id="soc-1",
            employee_id="sal-1",
            document_type="attestation_emploi",
            category="attestation_courante",
            employee_data=SALARIEE,
            company_data=SOCIETE,
            context=LE_5_NOVEMBRE,
            persist=False,
        )
