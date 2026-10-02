"""À la création d'un départ, pas de document chiffré sans bulletin de sortie.

Le solde de tout compte et l'attestation France Travail reprennent les sommes
du bulletin du mois de sortie. Produits à la création sur une estimation, ils
restaient téléchargeables alors que l'écran grise leur génération « tant que
le bulletin de sortie n'existe pas » (02/10/2026, fin de CDD). Le certificat de
travail, sans montant, est produit dans tous les cas.
"""

from unittest.mock import MagicMock, patch

from app.modules.employee_exits.application import commands as c

_EXIT = {
    "id": "exit-1", "employee_id": "emp-1", "exit_type": "fin_cdd",
    "last_working_day": "2026-09-11", "employees": {"id": "emp-1"},
}


def _creer(bulletin):
    generateur = MagicMock()
    generateur.generate_certificat_travail.return_value = b"%PDF"
    generateur.generate_attestation_pole_emploi.return_value = b"%PDF"
    generateur.generate_solde_tout_compte.return_value = b"%PDF"
    repo = MagicMock()
    repo.get_with_employee.return_value = dict(_EXIT)
    calcul = MagicMock()
    calcul.calculate.return_value = {}
    with patch.object(c, "EmployeeExitRepository", return_value=repo), patch.object(
        c, "ExitDocumentRepository", return_value=MagicMock()
    ), patch.object(c, "get_exit_document_generator", return_value=generateur), patch.object(
        c, "get_indemnity_calculator", return_value=calcul
    ), patch.object(c, "get_exit_storage_provider", return_value=MagicMock()), patch.object(
        c, "get_company_by_id", return_value={}
    ), patch.object(c, "document_service", MagicMock()), patch.object(
        c, "_run_portability_exit_documents"
    ), patch.object(c, "bulletin_du_mois_de_sortie", return_value=bulletin):
        c._run_post_create_indemnities_and_docs("exit-1", "co-1", "user-1", MagicMock())
    return generateur


def test_sans_bulletin_de_sortie_seul_le_certificat_est_produit():
    generateur = _creer(None)
    generateur.generate_certificat_travail.assert_called_once()
    generateur.generate_solde_tout_compte.assert_not_called()
    generateur.generate_attestation_pole_emploi.assert_not_called()


def test_avec_bulletin_de_sortie_les_trois_documents_sont_produits():
    generateur = _creer({"year": 2026, "month": 9})
    generateur.generate_certificat_travail.assert_called_once()
    generateur.generate_solde_tout_compte.assert_called_once()
    generateur.generate_attestation_pole_emploi.assert_called_once()
