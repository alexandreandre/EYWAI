"""Date de début du contrat déclarée (S21.G00.40.001).

Le cahier technique 2026.1 (§ 2.1.2.3.2) identifie un contrat par le salarié,
l'employeur, sa date de début et son numéro : un changement non déclaré en bloc
41 ouvre un second contrat chez les organismes. Quand le contrat en cours a
commencé chez le cabinet après l'embauche de la fiche (un CDD suivi d'un
apprentissage, sur une seule fiche), la DSN reprend la date du cabinet,
rangée dans la reprise DSN de la fiche.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.dsn_export.application.builder import build_individu_from_payroll
from app.modules.dsn_export.application.signalement_builder import (
    construire_signalement,
)
from app.modules.dsn_export.domain.contract_map import debut_du_contrat
from app.modules.dsn_export.domain.settings import ContactDeclaration, DsnSettings
from app.modules.dsn_export.domain.signalements import SignalementAFaire

pytestmark = pytest.mark.unit

APPRENTI = {
    "id": "a1",
    "first_name": "Alix",
    "last_name": "IMAGINAIRE",
    "nir": "107010112345678",
    "sexe": "M",
    "date_naissance": "2007-01-15",
    "lieu_naissance": "LYON (69)",
    "adresse": {"rue": "2 rue Inventée", "ville": "LYON", "code_postal": "69002"},
    "hire_date": "2026-06-22",
    "contract_type": "Apprentissage",
    "statut": "Non-Cadre",
    "duree_hebdomadaire": 35.0,
    "classification_conventionnelle": {"pcs": "674a", "idcc": "0292", "numero_contrat_dsn": "00004"},
}


def _avec_reprise(salarie, **reprise):
    return {**salarie, "specificites_paie": {"dsn_reprise": reprise}}


def test_sans_reprise_le_contrat_commence_a_l_embauche():
    assert debut_du_contrat(APPRENTI) == "2026-06-22"


def test_le_debut_repris_du_cabinet_l_emporte_sur_l_embauche():
    salarie = _avec_reprise(APPRENTI, date_debut_contrat="2026-08-31")
    assert debut_du_contrat(salarie) == "2026-08-31"


def test_un_debut_repris_avant_l_embauche_est_ecarte():
    # La fiche a changé de contrat depuis la reprise : l'embauche fait foi.
    salarie = _avec_reprise(APPRENTI, date_debut_contrat="2026-01-05")
    assert debut_du_contrat(salarie) == "2026-06-22"


def test_un_debut_repris_illisible_est_ecarte():
    salarie = _avec_reprise(APPRENTI, date_debut_contrat="31/08/2026")
    assert debut_du_contrat(salarie) == "2026-06-22"


def _individu(salarie, period="2026-10"):
    individu, _ = build_individu_from_payroll(
        salarie,
        {"salaire_brut": 1200.0, "synthese_net": {"net_imposable": 1000.0}},
        period=period,
        company_siret="49861035100015",
    )
    return individu


def test_la_dsn_declare_le_debut_du_contrat_du_cabinet():
    individu = _individu(_avec_reprise(APPRENTI, date_debut_contrat="2026-08-31"))
    assert individu.contrats[0].rubriques["S21.G00.40.001"] == "31082026"


def test_un_contrat_commence_avant_le_mois_garde_le_mois_entier():
    individu = _individu(_avec_reprise(APPRENTI, date_debut_contrat="2026-08-31"))
    remuneration = individu.contrats[0].versements[0].remunerations[0]
    assert remuneration.rubriques["S21.G00.51.001"] == "01102026"


def test_un_contrat_commence_dans_le_mois_part_de_son_premier_jour():
    individu = _individu(_avec_reprise(APPRENTI, date_debut_contrat="2026-08-31"), period="2026-08")
    remuneration = individu.contrats[0].versements[0].remunerations[0]
    assert remuneration.rubriques["S21.G00.51.001"] == "31082026"


SOCIETE = {"siret": "49861035100015", "name": "Société test", "code_naf": "2229A",
           "address": {"rue": "1 rue du Test", "code_postal": "01100", "ville": "OYONNAX"}}
REGLAGES = DsnSettings(contacts_declaration=[ContactDeclaration(
    nom="CONTACT PAIE", telephone="0400000000", email="paie@exemple.fr", code_destinataire="01")])


def test_un_signalement_d_arret_declare_le_meme_debut_de_contrat():
    arret = SignalementAFaire("a1", "04", "01", date(2026, 10, 5), date(2026, 10, 16), False,
                              date(2026, 10, 6), date(2026, 10, 11), None)
    texte = construire_signalement(SOCIETE, _avec_reprise(APPRENTI, date_debut_contrat="2026-08-31"),
                                   arret, settings=REGLAGES, essai=True, constitue_le=date(2026, 10, 7))
    lignes = dict(ligne.split(",", 1) for ligne in texte.strip().splitlines())
    assert lignes["S21.G00.40.001"] == "'31082026'"
