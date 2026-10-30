"""Le fichier d'essai de la DSN se génère malgré le verrou du dépôt réel.

Décision du 30/10/2026 : le verrou se lève quand octobre est validé, que
DSN-VAL dit 0 erreur bloquante et que le dépôt d'essai est accepté. L'essai
vient donc avant la levée : il ne vaut pas déclaration (S10.G00.00.005 = 01),
il ne compte pas comme la DSN du mois et ne crée pas de suivi de dépôt.
"""

from unittest.mock import patch

import pytest

from app.modules.dsn_export.domain.etat_conformite import message_non_deposable
from app.modules.exports.application import queries, service
from app.modules.exports.infrastructure.export_dsn import check_dsn_data
from app.modules.exports.schemas.requests import ExportGenerateRequest

pytestmark = pytest.mark.unit

SOCIETE = {"siret": "73282932000074", "code_naf": "2229A",
           "address": {"rue": "1 rue", "ville": "Lyon", "code_postal": "69000"}}


def _verrou(anomalies):
    return [a for a in anomalies if a["message"] == message_non_deposable()]


def test_le_fichier_reel_reste_bloque():
    anomalies, _ = check_dsn_data("c", "2026-10", [], SOCIETE)
    assert len(_verrou(anomalies)) == 1


def test_le_fichier_d_essai_passe_le_verrou_et_le_dit():
    anomalies, avertissements = check_dsn_data("c", "2026-10", [], SOCIETE, essai=True)
    assert _verrou(anomalies) == []
    assert any("essai" in a and "ne vaut pas déclaration" in a for a in avertissements)


APERCU = {
    "period": "2026-10", "dsn_type": "dsn_mensuelle_normale", "nombre_salaries": 0,
    "masse_salariale_brute": 0, "total_net_imposable": 0,
    "anomalies": [], "warnings": [], "can_generate": True,
}
TOTAUX = {"nombre_salaries": 0, "masse_salariale_brute": 0, "total_charges": 0,
          "total_net_imposable": 0, "total_pas": 0}


def _generer(filters):
    requete = ExportGenerateRequest(export_type="dsn_mensuelle", period="2026-10", filters=filters)
    with patch.object(service.providers, "preview_dsn", return_value=APERCU) as apercu, patch.object(
        service.providers, "generate_dsn_xml", return_value=b"S10.G00.00.001,'Martine Paie'"
    ) as fichier, patch.object(service, "upload_export_file", side_effect=lambda b, chemin, *a: chemin), patch.object(
        service, "create_signed_url", return_value="https://lien"
    ), patch.object(service.providers, "get_company_data", return_value={"siret": "1"}), patch.object(
        service.providers, "get_dsn_employees_data", return_value=([], TOTAUX)
    ), patch.object(service.commands, "record_export_history", return_value="exp-1") as historique, patch.object(
        service, "_record_dsn_transmission",
        return_value={"transmission_id": "t", "status": "manual", "mode": "manual", "message": "m"},
    ) as suivi:
        reponse = service._generate_dsn("co-1", "user-1", "Gaëlle", requete)
    return reponse, apercu, fichier, historique, suivi


def test_un_essai_se_genere_comme_essai_sans_compter_comme_la_dsn_du_mois():
    reponse, apercu, fichier, historique, suivi = _generer({"essai": True})
    assert apercu.call_args.kwargs.get("essai") is True
    assert fichier.call_args.kwargs.get("essai") is True
    assert reponse.files[0].filename.startswith("dsn_essai_mensuelle_2026_10")
    (ligne,), _ = historique.call_args
    assert ligne["parameters"]["essai"] is True
    suivi.assert_not_called()
    assert "ne vaut pas déclaration" in reponse.message_teletransmission


def test_sans_drapeau_le_fichier_est_reel():
    reponse, apercu, fichier, historique, suivi = _generer({})
    assert apercu.call_args.kwargs.get("essai") is False
    assert fichier.call_args.kwargs.get("essai") is False
    assert reponse.files[0].filename.startswith("dsn_mensuelle_2026_10")
    (ligne,), _ = historique.call_args
    assert ligne["parameters"]["essai"] is False
    suivi.assert_called_once()


def test_l_apercu_d_un_essai_lit_le_drapeau():
    requete = ExportGenerateRequest(export_type="dsn_mensuelle", period="2026-10", filters={"essai": True})
    with patch.object(queries.providers, "preview_dsn", return_value=APERCU) as apercu:
        queries.preview_export("co-1", requete)
    assert apercu.call_args.kwargs.get("essai") is True
