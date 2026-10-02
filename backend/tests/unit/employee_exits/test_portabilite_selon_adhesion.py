"""Pas d'attestation de portabilité mutuelle pour un salarié qui n'y adhère pas.

La recette du 02/10/2026 a vu une attestation de portabilité mutuelle produite
pour une fin de CDD sans adhésion à la mutuelle : le document affirmait une
couverture que le salarié n'a jamais eue. Le bulletin, lui, ne cotise à la
mutuelle que si la fiche porte l'adhésion ; l'attestation suit la même fiche.
"""

from unittest.mock import MagicMock, patch

from app.modules.employee_exits.application import commands as c


def _documents_demandes(specificites_paie):
    service = MagicMock()
    service.generate_document.return_value = {"is_eywai_template": False}
    with patch.object(c, "document_service", service):
        c._run_portability_exit_documents(
            exit_id="exit-1",
            company_id="co-1",
            current_user_id="user-1",
            sb=MagicMock(),
            exit_full_data={"last_working_day": "2026-09-11"},
            employee_full_data={"id": "emp-1", "specificites_paie": specificites_paie},
            company_data={},
            exit_type="fin_cdd",
            employee_id_exit="emp-1",
            storage=MagicMock(),
            doc_repo=MagicMock(),
        )
    return [appel.kwargs["document_type"] for appel in service.generate_document.call_args_list]


def test_sans_adhesion_pas_d_attestation_mutuelle():
    demandes = _documents_demandes({"mutuelle": {"adhesion": False}})
    assert "attestation_portabilite_mutuelle" not in demandes
    assert "attestation_portabilite_prevoyance" in demandes


def test_avec_adhesion_les_deux_attestations():
    demandes = _documents_demandes({"mutuelle": {"adhesion": True}})
    assert demandes == ["attestation_portabilite_mutuelle", "attestation_portabilite_prevoyance"]
