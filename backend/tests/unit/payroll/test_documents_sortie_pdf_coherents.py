"""Les PDF de sortie gardent leurs mentions et n'inventent pas de temps travaillé.

Notice France Travail DAJ 1250, mars 2025, rubrique 6.1 (ouverte le 05/11/2026) :
temps travaillé du bulletin ; les absences sont des périodes sous contrat,
pas la retenue qui retire les jours avant l'entrée ou après la sortie.
https://entreprise.francetravail.fr/accueil/assets/documents/DAJ%201250%20-%20mars%202025.pdf
"""

import io
from unittest.mock import MagicMock

import pdfplumber
import pytest

from app.modules.payroll.documents.attestation_employeur_salary_history import (
    get_salary_history,
)
from app.modules.payroll.solde_de_tout_compte.document_generator import (
    EmployeeExitDocumentGenerator,
)

pytestmark = pytest.mark.unit

SALARIE = {
    "id": "salarie-qa",
    "first_name": "Jeanne",
    "last_name": "Essai",
    "hire_date": "2026-06-29",
    "date_naissance": "1985-03-16",
    "job_title": "Responsable qualité et méthodes",
    "contract_type": "CDD",
    "salaire_de_base": {"valeur": 3000},
    "duree_hebdomadaire": 35,
}
SOCIETE = {
    "company_name": "Société QA",
    "siret": "12345678900011",
    "adresse_rue": "5 rue du Port",
    "adresse_code_postal": "44000",
    "adresse_ville": "Nantes",
    "city": "Nantes",
}
SORTIE = {"exit_type": "fin_cdd", "last_working_day": "2026-09-30"}


def _historique(bulletin):
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"year": 2026, "month": 6, "payslip_data": bulletin}
    ]
    return get_salary_history(
        "salarie-qa", SALARIE, "2026-06-30", supabase_client=client
    )["months"][0]


def test_un_bulletin_sans_quantite_ne_devient_pas_un_mois_de_151_heures():
    mois = _historique(
        {
            "salaire_brut": 272.73,
            "calcul_du_brut": [
                {"libelle": "Salaire de base (forfait jour)", "gain": 3000, "quantite": None}
            ],
            "details_absences": [
                {
                    "libelle": "Absence pour entrée ou sortie",
                    "quantite": 20,
                    "is_entree_sortie": True,
                    "perte": 2727.27,
                }
            ],
        }
    )
    assert mois["working_time"] == "Non renseigné"
    assert mois["absences"] == "Néant"
    assert mois["gross_salary"] == 272.73
    assert mois["period_label"] == "Juin 2026 (du 29/06/2026 au 30/06/2026)"


@pytest.mark.parametrize("avec_marqueur", [True, False])
def test_la_retenue_d_entree_ne_cache_pas_une_vraie_absence(avec_marqueur):
    entree = {"libelle": "Absence pour entrée ou sortie", "quantite": 20}
    if avec_marqueur:
        entree["is_entree_sortie"] = True
    mois = _historique(
        {
            "salaire_brut": 136.36,
            "nombre_jours_travailles": 1,
            "details_absences": [entree, {"libelle": "Maladie", "quantite": 1, "unite": "jours"}],
        }
    )
    assert mois["working_time"] == "1.00 jour"
    assert mois["absences"] == "1.00 jour"


@pytest.mark.parametrize("champ, attendu", [("heures_travaillees", "0.00 h"), ("nombre_jours_travailles", "0.00 jours")])
def test_un_temps_explicitement_nul_reste_nul(champ, attendu):
    mois = _historique({"salaire_brut": 100, champ: 0})
    assert mois["working_time"] == attendu


def test_le_certificat_standard_tient_sur_une_page_avec_sa_mention_legale():
    pdf = EmployeeExitDocumentGenerator().generate_certificat_travail(
        SALARIE, SOCIETE, SORTIE
    )
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        assert len(doc.pages) == 1
        texte = doc.pages[0].extract_text()
        assert "Signature et cachet" in texte
        assert "Article L1234-19" in texte
        assert "Portabilité des garanties" in texte


@pytest.mark.parametrize("organismes", [{}, {"mutuelle_nom": "Santé QA", "prevoyance_nom": "Prévoyance QA"}])
def test_la_portabilite_n_a_pas_de_phrase_cassee_sans_organisme(organismes):
    pdf = EmployeeExitDocumentGenerator().generate_attestation_pole_emploi(
        SALARIE, {**SOCIETE, **organismes}, SORTIE, supabase_client=None
    )
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        texte = " ".join(" ".join((p.extract_text() or "").split()) for p in doc.pages)
    assert "auprès de organisme" not in texte
    if organismes:
        assert "Santé QA" in texte
        assert "Prévoyance QA" in texte
    else:
        assert "auprès de l'organisme complémentaire santé de l'entreprise" in texte
        assert "de l'organisme de prévoyance de l'entreprise" in texte
