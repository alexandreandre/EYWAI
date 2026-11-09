"""R-467, R-466 : une lecture qui échoue arrête la DSN, elle ne l'appauvrit pas en silence.

Le paramétrage DSN illisible était rendu vide et l'export continuait ; un code BOETH illisible
disparaissait du fichier sans un mot. Le premier s'arrête, le second s'affiche et s'arrête aussi :
une DSN déposée sans ce qu'on n'a pas su lire ne dit plus la vérité. Une ligne absente (société
pas encore paramétrée) n'est pas une erreur : la société dit ses manques comme avant.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.dsn_export.domain.settings import DsnSettings
from app.modules.dsn_export.infrastructure import settings_repository as repo
from app.modules.exports.infrastructure import export_dsn

SOCIETE = {
    "siret": "12345678900015",
    "code_naf": "2562B",
    "name": "ACME",
    "address": {"rue": "1 RUE", "code_postal": "75001", "ville": "PARIS"},
    "urssaf": "123456789012345678",
}


def test_le_parametrage_illisible_leve_au_lieu_de_rendre_vide():
    with patch.object(repo, "supabase") as base:
        base.table.side_effect = RuntimeError("réseau")
        with pytest.raises(repo.ParametrageDsnIllisible, match="paramétrage DSN"):
            repo.charger("soc")


def test_une_societe_sans_ligne_reste_vide_et_dit_ses_manques():
    with patch.object(repo, "supabase") as base:
        base.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        assert repo.charger("soc") == DsnSettings()


def _salarie(eid="e1", **fiche):
    return {
        "employee": {"id": eid, "first_name": "P", "last_name": "N", "nir": "1850175123456", **fiche},
        "payslip_data": {},
    }


def test_l_apercu_dit_que_le_parametrage_est_illisible_et_bloque():
    with patch.object(
        export_dsn.settings_repository, "charger", side_effect=repo.ParametrageDsnIllisible("x")
    ):
        anomalies, _ = export_dsn.check_dsn_data("soc", "2026-11", [], SOCIETE)
    bloquantes = [a for a in anomalies if a["severity"] == "blocking"]
    assert any("paramétrage DSN" in a["message"].lower() or "x" == a["message"] for a in bloquantes)


def test_le_fichier_ne_se_produit_pas_sans_parametrage():
    with patch.object(export_dsn, "get_company_data", return_value=SOCIETE), patch.object(
        export_dsn, "get_dsn_employees_data", return_value=([], {})
    ), patch.object(export_dsn, "raison_de_refus_dsn_mois_repris", return_value=None), patch.object(
        export_dsn.settings_repository, "charger", side_effect=repo.ParametrageDsnIllisible("illisible")
    ), patch.object(export_dsn, "build_parsed_dsn_from_payroll") as construire:
        with pytest.raises(ValueError, match="illisible"):
            export_dsn.generate_dsn_file("soc", "2026-11", "dsn_mensuelle_normale", essai=True)
    construire.assert_not_called()


def test_un_code_boeth_illisible_se_note_sur_la_fiche():
    with patch.object(
        export_dsn.oeth_queries, "get_boeth_code_for_employee", side_effect=RuntimeError("réseau")
    ):
        fiche = export_dsn._fiche_dsn({"id": "e1"}, "2026-11")
    assert fiche["boeth_illisible"] is True


def test_un_salarie_sans_boeth_n_est_pas_une_anomalie():
    with patch.object(export_dsn.oeth_queries, "get_boeth_code_for_employee", return_value=None):
        fiche = export_dsn._fiche_dsn({"id": "e1"}, "2026-11")
    assert "boeth_illisible" not in fiche


def test_l_apercu_nomme_le_salarie_dont_le_boeth_est_illisible_et_bloque():
    donnees = [_salarie(boeth_illisible=True, contract_type="CDI")]
    with patch.object(export_dsn.settings_repository, "charger", return_value=DsnSettings()):
        anomalies, _ = export_dsn.check_dsn_data("soc", "2026-11", donnees, SOCIETE, essai=True)
    assert [a for a in anomalies if a["severity"] == "blocking" and "BOETH" in a["message"] and a["employee_id"] == "e1"]


def test_le_fichier_ne_part_pas_avec_un_boeth_illisible():
    donnees = [_salarie(boeth_illisible=True)]
    with patch.object(export_dsn, "get_company_data", return_value=SOCIETE), patch.object(
        export_dsn, "get_dsn_employees_data", return_value=(donnees, {})
    ), patch.object(export_dsn, "raison_de_refus_dsn_mois_repris", return_value=None), patch.object(
        export_dsn.settings_repository, "charger", return_value=DsnSettings()
    ), patch.object(export_dsn, "build_parsed_dsn_from_payroll") as construire:
        with pytest.raises(ValueError, match="BOETH"):
            export_dsn.generate_dsn_file("soc", "2026-11", "dsn_mensuelle_normale", essai=True)
    construire.assert_not_called()
