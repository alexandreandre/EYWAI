"""Régénérer une attestation de salaire : nouvelle date, bon premier jour d'arrêt."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.absences.infrastructure import providers

pytestmark = pytest.mark.unit


def _client(existante):
    client = MagicMock()
    mises_a_jour = []
    reponses = {
        "absence_requests": {"employee_id": "e1", "company_id": "c1", "type": "arret_maladie",
                             "selected_days": ["2026-08-20", "2026-08-17", "2026-08-18"]},
        "employees": {"id": "e1"},
        "companies": {"id": "c1"},
    }

    def table(nom):
        t = MagicMock()
        if nom == "salary_certificates":
            t.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=existante)

            def update(data):
                mises_a_jour.append(data)
                u = MagicMock()
                u.eq.return_value.execute.return_value = MagicMock(data=[{"id": "cert-1"}])
                return u

            t.update.side_effect = update
        else:
            t.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=reponses[nom])
        return t

    client.table.side_effect = table
    return client, mises_a_jour


def test_la_regeneration_date_la_nouvelle_version_et_part_du_premier_jour():
    client, mises_a_jour = _client({"id": "cert-1", "storage_path": "e1/ancienne.pdf"})
    generateur = MagicMock()
    generateur.generate_salary_certificate.return_value = b"pdf"
    with patch.object(providers, "supabase", client), patch.object(
        providers, "SalaryCertificateGenerator", return_value=generateur
    ):
        cert = providers.SalaryCertificateProvider().generate_for_absence(
            "arret-1", generated_by="rh-1", replace_existing=True
        )
    assert cert == "cert-1"
    assert generateur.get_reference_salary.call_args.args == ("e1", date(2026, 8, 17))
    assert mises_a_jour[0]["generated_at"].startswith(date.today().isoformat()[:4])
    client.storage.from_.return_value.remove.assert_called_once_with(["e1/ancienne.pdf"])
