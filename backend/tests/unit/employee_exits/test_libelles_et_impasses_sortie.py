"""[H14] Libellés périmés et impasses de l'écran des départs.

- La checklist écrivait « Attestation Pôle Emploi » quand l'écran, les documents
  et la DSN disent « France Travail » (l'opérateur a changé de nom le
  01/01/2024) : le libellé des nouveaux départs change, une migration (non
  appliquée) renomme les tâches déjà créées.
- L'attestation de portabilité prévoyance était générée pour tout salarié, même
  sans prévoyance sur sa fiche : le document affirmait une couverture que le
  salarié n'a pas. Le bulletin ne cotise à la prévoyance que si la fiche porte
  l'adhésion (`specificites_paie.prevoyance.adhesion`) ; l'attestation suit la
  même fiche, comme celle de la mutuelle.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application import commands as c
from app.modules.employee_exits.application.service import DEFAULT_CHECKLIST_ITEMS

pytestmark = pytest.mark.unit

_MIGRATIONS = Path(__file__).resolve().parents[4] / "supabase" / "migrations"


def test_la_checklist_dit_france_travail():
    libelles = [item["item_label"] for item in DEFAULT_CHECKLIST_ITEMS]
    assert "Attestation France Travail" in libelles
    assert not any("Pôle Emploi" in libelle for libelle in libelles)


def test_une_migration_renomme_les_taches_deja_creees():
    (fichier,) = sorted(_MIGRATIONS.glob("*_checklist_attestation_france_travail.sql"))
    sql = fichier.read_text(encoding="utf-8")
    assert "UPDATE public.exit_checklist_items" in sql
    assert "'Attestation France Travail'" in sql
    assert "item_code = 'unemployment_certificate'" in sql


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


def test_sans_prevoyance_sur_la_fiche_pas_d_attestation_de_portabilite_prevoyance():
    demandes = _documents_demandes({"mutuelle": {"adhesion": True}})
    assert demandes == ["attestation_portabilite_mutuelle"]

    demandes = _documents_demandes({"mutuelle": {"adhesion": True}, "prevoyance": {"adhesion": False}})
    assert demandes == ["attestation_portabilite_mutuelle"]


def test_avec_prevoyance_sur_la_fiche_l_attestation_est_generee():
    demandes = _documents_demandes({"prevoyance": {"adhesion": True}})
    assert demandes == ["attestation_portabilite_prevoyance"]
