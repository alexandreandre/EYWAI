"""Le changement de code PCS-ESE déclaré dans le bloc « Changements Contrat » (S21.G00.41).

Cahier technique 2026.1.2 : bloc 41 « à renseigner en cas de modification d'une caractéristique
du contrat », avec « la valeur avant changement » (p. 215) ; date de la modification obligatoire
et profondeur de recalcul obligatoire pour un bloc seul (p. 26) ; place du bloc juste après le
contrat, avant les arrêts (structure, p. 6552 du texte). Guide OETH de l'Urssaf (v2.5, p. 46) :
profondeur « au premier jour du mois où le changement […] est constaté ».
"""

from __future__ import annotations

import copy

from app.modules.dsn_export.application.builder import build_parsed_dsn_from_payroll
from app.modules.dsn_export.domain.changement_pcs import bloc_changement_pcs as b
from app.modules.dsn_export.domain.writer import serialize_dsn_file

SOCIETE = {
    "siret": "12345678900015",
    "name": "ACME INDUSTRIE",
    "code_naf": "2562B",
    "address": {"rue": "1 RUE DE LA PAIX", "code_postal": "75001", "ville": "PARIS"},
}


def _sample_company():
    return copy.deepcopy(SOCIETE)


def _sample_employee_row():
    return {
        "employee": {
            "id": "emp-1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "nir": "1850175123456",
            "sexe": "M",
            "date_naissance": "1985-01-15",
            "lieu_naissance": "PARIS",
            "contract_type": "CDI",
            "hire_date": "2020-01-01",
            "statut": "Non-Cadre",
            "adresse": {"rue": "10 AVENUE TEST", "code_postal": "75010", "ville": "PARIS"},
            "idcc": "1486",
            "pcs": "389a",
            "job_title": "Technicien",
        },
        "payslip_data": {
            "salaire_brut": 2500.0,
            "heures_remunerees": 151.67,
            "synthese_net": {"net_imposable": 2000.0, "net_a_payer": 1850.0},
        },
    }

C = {"pcs": "674a", "pcs_changement": {"ancien": "9999", "date": "2026-11-06"}}


def test_bloc_du_mois():
    bloc = b(C, "674a", "2026-11", None)
    assert bloc.date_modification == "06112026"
    assert bloc.rubriques == {
        "S21.G00.41.001": "06112026",
        "S21.G00.41.019": "9999",
        "S21.G00.41.028": "01112026",
    }


def test_mois_suivant_tant_que_rien_n_est_depose():
    assert b(C, "674a", "2026-12", "2026-10") is not None


def test_deja_declare():
    assert b(C, "674a", "2026-12", "2026-11") is None


def test_changement_apres_le_mois_declare():
    assert b(C, "674a", "2026-10", None) is None


def test_ancien_egal_actuel_ou_absent():
    meme = {"pcs": "9999", "pcs_changement": {"ancien": "9999", "date": "2026-11-06"}}
    assert b(meme, "9999", "2026-11", None) is None
    assert b({"pcs": "674a"}, "674a", "2026-11", None) is None
    assert b({}, "", "2026-11", None) is None


def _ligne_employe_change():
    row = copy.deepcopy(_sample_employee_row())
    row["employee"]["pcs"] = "674a"
    row["employee"]["classification_conventionnelle"] = copy.deepcopy(C)
    return row


def test_la_dsn_porte_le_bloc_juste_apres_le_contrat():
    dsn_file, _ = build_parsed_dsn_from_payroll(_sample_company(), [_ligne_employe_change()], "2026-11")
    lignes = [l.split(",")[0] for l in serialize_dsn_file(dsn_file).split("\r\n") if "," in l]
    i = lignes.index("S21.G00.41.001")
    assert lignes[i : i + 3] == ["S21.G00.41.001", "S21.G00.41.019", "S21.G00.41.028"]
    assert lignes[i - 1].startswith("S21.G00.40.")
    assert all(not r.startswith("S21.G00.40.") for r in lignes[i + 3 :])
    texte = serialize_dsn_file(dsn_file)
    assert "S21.G00.41.019,'9999'" in texte and "S21.G00.40.004,'674a'" in texte


def test_rien_d_ecrit_quand_le_changement_est_deja_parti():
    dsn_file, _ = build_parsed_dsn_from_payroll(
        _sample_company(), [_ligne_employe_change()], "2026-12", derniere_periode_deposee="2026-11"
    )
    assert "S21.G00.41" not in serialize_dsn_file(dsn_file)


def test_aucun_bloc_sans_changement():
    dsn_file, _ = build_parsed_dsn_from_payroll(_sample_company(), [_sample_employee_row()], "2026-11")
    assert "S21.G00.41" not in serialize_dsn_file(dsn_file)


def test_avis_de_l_apercu():
    from app.modules.dsn_export.domain.changement_pcs import avis_changements_pcs

    lignes = [_ligne_employe_change(), _ligne_employe_change(), _sample_employee_row()]
    assert avis_changements_pcs(lignes, "2026-11", None) == (
        "Code PCS-ESE changé pour 2 salariés : la DSN déclare l'ancien code "
        "(bloc Changements Contrat, S21.G00.41)."
    )
    assert avis_changements_pcs(lignes[:1], "2026-11", None).startswith("Code PCS-ESE changé pour 1 salarié :")
    assert avis_changements_pcs(lignes, "2026-12", "2026-11") is None
