"""Modifier un document de sortie : l'enregistrement aboutit, l'historique se garde.

L'édition écrivait dans des colonnes absentes de la table (document_data,
version, manually_edited, last_edited_*) et réécrivait le PDF sans remplacement
autorisé : la modification échouait toujours.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application import commands, queries

pytestmark = pytest.mark.unit

# Colonnes de la table exit_documents sur la base de test (information_schema, 28/09/2026).
COLONNES_EXIT_DOCUMENTS = {
    "id", "exit_id", "company_id", "document_type", "document_category", "storage_path",
    "filename", "mime_type", "file_size_bytes", "generation_template", "generation_data",
    "generated_at", "uploaded_by", "upload_notes", "is_signed", "signature_date",
    "is_transmitted", "transmission_date", "created_at", "updated_at",
    "published_to_employee", "published_at", "published_by",
}


def _document(**modifs):
    doc = {
        "id": "doc-1",
        "exit_id": "exit-1",
        "company_id": "co-1",
        "document_type": "certificat_travail",
        "document_category": "generated",
        "storage_path": "exits/exit-1/certificat_travail.pdf",
        "generation_data": None,
    }
    doc.update(modifs)
    return doc


@pytest.fixture
def infra():
    doc_repo = MagicMock()
    exit_repo = MagicMock()
    exit_repo.get_by_id.return_value = {"id": "exit-1", "employee_id": "e1", "exit_type": "fin_cdd"}
    stockage = MagicMock()
    generateur = MagicMock()
    generateur.generate_certificat_travail.return_value = b"pdf"
    with (
        patch.object(commands, "ExitDocumentRepository", return_value=doc_repo),
        patch.object(commands, "EmployeeExitRepository", return_value=exit_repo),
        patch.object(commands, "get_exit_storage_provider", return_value=stockage),
        patch.object(commands, "get_exit_document_generator", return_value=generateur),
        patch.object(commands, "get_employee_full", return_value={"first_name": "Jeanne"}),
        patch.object(commands, "get_company_by_id", return_value={"company_name": "Société QA"}),
    ):
        yield {"doc_repo": doc_repo, "stockage": stockage, "generateur": generateur}


def _editer(doc_repo, doc, **demande):
    doc_repo.get_by_id.return_value = doc
    return commands.edit_exit_document(
        "exit-1", "doc-1", "co-1",
        {"document_data": {"employee": {"job_title": "Préparatrice peinture"}}, **demande},
        "rh-1",
        supabase_client=MagicMock(),
    )


def test_l_edition_n_ecrit_que_des_colonnes_de_la_table(infra):
    resultat = _editer(infra["doc_repo"], _document(), changes_summary="Intitulé du poste")

    ecrit = infra["doc_repo"].update.call_args.args[3]
    assert set(ecrit) <= COLONNES_EXIT_DOCUMENTS
    donnees = ecrit["generation_data"]
    assert donnees["employee"] == {"job_title": "Préparatrice peinture"}
    assert [(h["version"], h["changes_summary"]) for h in donnees["_edit_history"]] == [(2, "Intitulé du poste")]
    assert resultat["version"] == 2
    # Le PDF est réécrit à sa place, remplacement autorisé.
    assert infra["stockage"].upload.call_args.kwargs == {"remplacer": True}
    gen_employee = infra["generateur"].generate_certificat_travail.call_args.args[0]
    assert gen_employee["job_title"] == "Préparatrice peinture"


def test_une_seconde_edition_prolonge_l_historique(infra):
    deja = _document(generation_data={
        "employee": {"job_title": "Préparatrice"},
        "_edit_history": [{"version": 2, "edited_at": "2026-09-28T10:00:00+00:00", "edited_by": "rh-1",
                           "changes_summary": "Première"}],
    })
    resultat = _editer(infra["doc_repo"], deja, changes_summary="Seconde")
    historique = infra["doc_repo"].update.call_args.args[3]["generation_data"]["_edit_history"]
    assert [h["version"] for h in historique] == [2, 3]
    assert resultat["version"] == 3


def test_les_cles_techniques_envoyees_par_l_ecran_ne_sont_pas_gardees(infra):
    _editer(infra["doc_repo"], _document(), document_data={
        "employee": {"job_title": "X"}, "_bulletin_de_sortie": {"mois": "07/2026"}, "_edit_history": [],
    })
    donnees = infra["doc_repo"].update.call_args.args[3]["generation_data"]
    assert "_bulletin_de_sortie" not in donnees


def test_les_details_rendent_la_version_et_signalent_le_bulletin_de_sortie():
    doc = _document(
        document_type="solde_tout_compte",
        generation_data={"_edit_history": [{"version": 2, "edited_at": "2026-09-28T10:00:00+00:00",
                                            "edited_by": "rh-1", "changes_summary": "Adresse"}]},
    )
    doc_repo = MagicMock()
    doc_repo.get_by_id.return_value = doc
    exit_repo = MagicMock()
    exit_repo.get_by_id.return_value = {"employee_id": "e1", "last_working_day": "2026-07-24"}
    with (
        patch.object(queries, "ExitDocumentRepository", return_value=doc_repo),
        patch.object(queries, "EmployeeExitRepository", return_value=exit_repo),
        patch.object(queries, "get_exit_storage_provider", return_value=MagicMock()),
        patch(
            "app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie.bulletin_du_mois_de_sortie",
            return_value={"salaire_brut": 3509.91, "net_a_payer": 2785.59},
        ),
    ):
        details = queries.get_exit_document_details("exit-1", "doc-1", "co-1", supabase_client=MagicMock())
    assert details["version"] == 2 and details["manually_edited"] is True
    assert details["last_edited_by"] == "rh-1"
    assert details["document_data"]["_bulletin_de_sortie"] == {"mois": "07/2026", "net_a_payer": 2785.59}
    assert "_edit_history" not in details["document_data"]


def test_le_dossier_dit_ce_que_le_bulletin_de_sortie_a_verse():
    """Onglet Indemnités : l'estimation d'ouverture n'est pas ce qui a été payé."""
    exit_repo = MagicMock()
    exit_repo.get_with_employee.return_value = {
        "id": "exit-1", "employee_id": "e1", "last_working_day": "2026-07-24", "exit_type": "fin_cdd",
    }
    bulletin = {
        "salaire_brut": 3509.91,
        "net_a_payer": 2785.59,
        "calcul_du_brut": [
            {"libelle": "Salaire de base", "gain": 1551.06},
            {"libelle": "Ind.de précarité des CDD", "gain": 797.04},
            {"libelle": "Ind.de CP des CDD", "gain": 940.23},
        ],
    }
    with (
        patch.object(queries, "EmployeeExitRepository", return_value=exit_repo),
        patch.object(queries, "enrich_exit_with_documents_and_checklist"),
        patch(
            "app.modules.payroll.solde_de_tout_compte.common.bulletin_de_sortie.bulletin_du_mois_de_sortie",
            return_value=bulletin,
        ),
    ):
        dossier = queries.get_employee_exit("exit-1", "co-1", supabase_client=MagicMock())
    assert dossier["bulletin_de_sortie"] == {
        "mois": "07/2026",
        "salaire_brut": 3509.91,
        "net_a_payer": 2785.59,
        "sommes_de_rupture": [
            {"libelle": "Ind.de précarité des CDD", "montant": 797.04},
            {"libelle": "Ind.de CP des CDD", "montant": 940.23},
        ],
    }
