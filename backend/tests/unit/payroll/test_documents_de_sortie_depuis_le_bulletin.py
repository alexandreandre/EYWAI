"""Documents de sortie tirés du bulletin du mois de sortie.

Fin de CDD de juillet 2026, bulletin repris de l'ancien logiciel : le reçu pour
solde de tout compte affichait 2 584,10 € (salaire contractuel proratisé,
cotisations à zéro, indemnités d'un autre calcul) contre 2 785,59 € réellement
payés ; l'attestation France Travail inventait vingt mois de salaire avant
l'embauche, ne comptait que les heures sup et omettait la précarité.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock

import pdfplumber
import pytest

from app.modules.payroll.documents.attestation_employeur_salary_history import get_salary_history
from app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie import (
    est_une_somme_de_rupture,
    lignes_du_bulletin,
    sommes_de_rupture_du_bulletin,
)
from app.modules.payroll.solde_de_tout_compte.document_generator import (
    EmployeeExitDocumentGenerator,
)

pytestmark = pytest.mark.unit

# Bulletin de sortie repris tel quel (libellés de l'ancien logiciel).
BULLETIN_JUILLET = {
    "salaire_brut": 3509.91,
    "net_a_payer": 2785.59,
    "calcul_du_brut": [
        {"libelle": "H.Absence Congés Payés", "quantite": 7, "taux": 12.31, "gain": None, "perte": 86.17},
        {"libelle": "Réduction HS structurelles (jours d'absence)", "quantite": 0.8, "taux": 15.3875, "perte": 12.31},
        {"libelle": "Salaire de base", "quantite": 126, "taux": 12.31, "gain": 1551.06},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 14.4, "taux": 15.3875, "gain": 221.58},
        {"libelle": "SOUS-TOTAL SALAIRE CONTRACTUEL", "quantite": 140.4, "gain": 1772.64, "is_sous_total": True},
        {"libelle": "ARBITRAGE DES CONGES PAYES", "quantite": 98.48, "gain": 98.48},
        {"libelle": "Ind.de précarité des CDD", "quantite": 797.04, "taux": 100, "gain": 797.04},
        {"libelle": "Ind.de CP des CDD", "quantite": 940.23, "taux": 100, "gain": 940.23},
    ],
    "primes_non_soumises": [],
}

BULLETIN_AVRIL = {
    "salaire_brut": 2017.05,
    "calcul_du_brut": [
        {"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.31, "gain": 1867.06},
        {"libelle": "Heures suppl. structurelles majorées à 25%", "quantite": 17.33, "taux": 15.3875, "gain": 149.99},
    ],
}

SALARIE = {
    "id": "emp-cdd",
    "first_name": "Jeanne",
    "last_name": "Essai",
    "date_naissance": "1985-03-16",
    "hire_date": "2026-03-23",
    "job_title": "Préparatrice peinture",
    "contract_type": "CDD",
    "salaire_de_base": {"valeur": 1867.06},
    "duree_hebdomadaire": 39,
}
SOCIETE = {"company_name": "Société QA", "siret": "12345678900011", "city": "Belley"}
SORTIE = {"last_working_day": "2026-07-24", "exit_type": "fin_cdd", "notice_period_days": 0}


def _client(bulletins: dict[tuple[int, int], dict]) -> MagicMock:
    """Client Supabase de lecture : payslips filtrés par année et mois, ou tous."""
    client = MagicMock()

    class Requete:
        def __init__(self):
            self.filtres = {}

        def select(self, *_a, **_k):
            return self

        def eq(self, colonne, valeur):
            self.filtres[colonne] = valeur
            return self

        def limit(self, *_a):
            return self

        def execute(self):
            lignes = [
                {"year": a, "month": m, "payslip_data": d}
                for (a, m), d in bulletins.items()
                if self.filtres.get("year", a) == a and self.filtres.get("month", m) == m
            ]
            return MagicMock(data=lignes)

    client.table.side_effect = lambda _nom: Requete()
    return client


def _texte(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return "\n".join(page.extract_text() or "" for page in document.pages)


def test_les_sommes_de_rupture_se_reconnaissent_quel_que_soit_le_logiciel():
    assert est_une_somme_de_rupture("Ind.de précarité des CDD")
    assert est_une_somme_de_rupture("Ind.de CP des CDD")
    assert est_une_somme_de_rupture("Indemnité compensatrice de congés payés")
    assert est_une_somme_de_rupture("Indemnité compensatrice de préavis")
    assert not est_une_somme_de_rupture("ARBITRAGE DES CONGES PAYES")
    assert not est_une_somme_de_rupture("Salaire de base")


def test_les_lignes_du_bulletin_somment_au_brut():
    remuneration, rupture, apres = lignes_du_bulletin(BULLETIN_JUILLET)
    assert [l["label"] for l in rupture] == ["Ind.de précarité des CDD", "Ind.de CP des CDD"]
    assert "SOUS-TOTAL SALAIRE CONTRACTUEL" not in [l["label"] for l in remuneration]
    assert remuneration[0]["montant"] == -86.17
    assert round(sum(l["montant"] for l in remuneration + rupture), 2) == 3509.91
    assert apres == []


def test_les_retenues_d_absence_du_moteur_sont_lues():
    """Bulletin calculé : la sortie en cours de mois est une retenue d'absence."""
    bulletin = {
        "salaire_brut": 272.73,
        "net_a_payer": 195.15,
        "calcul_du_brut": [{"libelle": "Salaire de base (forfait jour)", "gain": 3000}],
        "details_absences": [
            {"libelle": "Absence pour entrée ou sortie", "quantite": 20.0, "taux": 136.3636, "perte": 2727.27}
        ],
    }
    remuneration, _rupture, _apres = lignes_du_bulletin(bulletin)
    assert [l["label"] for l in remuneration] == ["Salaire de base (forfait jour)", "Absence pour entrée ou sortie"]
    texte = _texte(
        EmployeeExitDocumentGenerator().generate_solde_tout_compte(
            SALARIE, SOCIETE, {**SORTIE, "last_working_day": "2026-06-30"}, {}, _client({(2026, 6): bulletin})
        )
    )
    assert "Autres éléments du bulletin" not in texte
    assert "la somme nette de 195.15 €" in texte


def test_le_recu_reprend_le_bulletin_de_sortie():
    pdf = EmployeeExitDocumentGenerator().generate_solde_tout_compte(
        SALARIE, SOCIETE, SORTIE, {}, _client({(2026, 7): BULLETIN_JUILLET})
    )
    texte = _texte(pdf)
    assert "la somme nette de 2 785.59 €" in texte
    assert "3 509.91 €" in texte and "724.32 €" in texte
    assert "797.04 €" in texte and "940.23 €" in texte
    assert "− 86.17 €" in texte
    assert "bulletin de paie de 07/2026" in texte


def test_sans_bulletin_de_sortie_le_recu_reste_une_estimation():
    indemnites = {"indemnite_conges": {"montant": 100.0, "jours_restants": 1}}
    pdf = EmployeeExitDocumentGenerator().generate_solde_tout_compte(
        SALARIE, SOCIETE, SORTIE, indemnites, _client({})
    )
    assert "Salaire du dernier mois" in _texte(pdf)


def test_une_indemnite_exoneree_s_ajoute_apres_cotisations():
    bulletin = {
        "salaire_brut": 2000.0,
        "net_a_payer": 6560.0,
        "calcul_du_brut": [{"libelle": "Salaire de base", "gain": 2000.0}],
        "indemnites_sortie": {"lignes_exonerees": [{"libelle": "Indemnité légale de licenciement", "montant": 5000.0}]},
    }
    remuneration, rupture, apres = lignes_du_bulletin(bulletin)
    assert [l["label"] for l in apres] == ["Indemnité légale de licenciement"]
    texte = _texte(
        EmployeeExitDocumentGenerator().generate_solde_tout_compte(
            SALARIE, SOCIETE, {**SORTIE, "exit_type": "licenciement"}, {}, _client({(2026, 7): bulletin})
        )
    )
    assert "Sommes versées après cotisations" in texte
    assert "440.00 €" in texte  # 2 000 + 5 000 − 6 560
    assert sommes_de_rupture_du_bulletin(bulletin) == [
        {"libelle": "Indemnité légale de licenciement", "montant": 5000.0, "dans_le_brut": False}
    ]


def test_l_attestation_france_travail_part_de_l_embauche_et_isole_la_rupture():
    historique = get_salary_history(
        "emp-cdd",
        SALARIE,
        "2026-07-24",
        supabase_client=_client({(2026, 4): BULLETIN_AVRIL, (2026, 7): BULLETIN_JUILLET}),
    )
    mois = [(m["year"], m["month"]) for m in historique["months"]]
    assert mois == [(2026, 3), (2026, 4), (2026, 5), (2026, 6), (2026, 7)]
    assert historique["months"][0]["period_label"] == "Mars 2026 (du 23/03/2026 au 31/03/2026)"
    avril, juillet = historique["months"][1], historique["months"][-1]
    assert avril["working_time"] == "169.00 h"
    assert juillet["working_time"] == "140.40 h"
    assert juillet["gross_salary"] == 1772.64
    assert [s["libelle"] for s in historique["sommes_de_rupture"]] == [
        "Ind.de précarité des CDD",
        "Ind.de CP des CDD",
    ]


def test_l_attestation_france_travail_declare_les_sommes_du_bulletin():
    texte = _texte(
        EmployeeExitDocumentGenerator().generate_attestation_pole_emploi(
            SALARIE,
            SOCIETE,
            {**SORTIE, "calculated_indemnities": {"indemnite_conges": {"montant": 1138.63}}},
            supabase_client=_client({(2026, 7): BULLETIN_JUILLET}),
        )
    )
    assert "Ind.de précarité des CDD 797.04 €" in texte
    assert "1 138.63" not in texte
    assert "2024" not in texte


@pytest.mark.parametrize("motif, mention", [("fin_cdd", True), ("demission", False)])
def test_le_certificat_de_travail_signale_la_portabilite(motif, mention):
    texte = _texte(
        EmployeeExitDocumentGenerator().generate_certificat_travail(
            SALARIE, SOCIETE, {**SORTIE, "exit_type": motif}
        )
    )
    assert ("Portabilité des garanties" in texte) is mention
