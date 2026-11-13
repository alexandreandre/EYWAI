"""Tests couverture DSN par entreprise."""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.dsn_import.application.coverage import (
    compute_coverage,
    count_timeline_coverage,
    expected_last_period,
    is_dsn_coverage_complete,
    merge_dsn_alerts_into_overview,
    resolve_next_import_period,
)
from app.shared.reprise_paie import Bascule


@pytest.fixture(autouse=True)
def sans_bascule_en_base():
    with patch('app.modules.dsn_import.application.coverage.lire_bascule', return_value=None):
        yield


def _couverture_reprise(cutoff, *, through=9, reference=date(2026, 11, 12), revoked_periods=()):
    company = {'id': 'societe-test', 'dsn_sync_mode': 'transition'}
    periods = [f'2026-{month:02d}' for month in range(1, through + 1)]
    batches = [{
        'id': 'import-test', 'status': 'committed',
        'summary': {'commit_report': {'target_company_id': 'societe-test'}, 'periods_committed': periods},
        'created_at': '2026-10-01T00:00:00Z',
    }]
    with patch('app.modules.dsn_import.application.coverage.lire_bascule', return_value=cutoff):
        return compute_coverage(company, batches=batches, reference=reference, revoked_periods=list(revoked_periods))


def test_revoquer_le_dernier_mois_affiche_le_dernier_encore_importe():
    cov = _couverture_reprise(Bascule(2026, 9), revoked_periods=['2026-09'])
    assert cov['last_period'] == '2026-08'
    assert cov['status'] == 'missing'
    assert cov['next_import_period'] == '2026-09'
    assert count_timeline_coverage(cov) == (8, 9)


def test_revoquer_tous_les_mois_ne_garde_pas_un_dernier_mois_fantome():
    cov = _couverture_reprise(
        Bascule(2026, 9), revoked_periods=[f'2026-{m:02d}' for m in range(1, 10)],
    )
    assert cov['last_period'] is None
    assert cov['months_covered'] == []
    assert cov['status'] == 'never'


def test_import_optionnel_apres_reprise_reste_present_sans_compter_comme_attendu():
    cov = _couverture_reprise(Bascule(2026, 9), through=10)
    assert cov['last_period'] == '2026-10'
    assert '2026-10' in cov['months_covered']
    assert cov['timeline'][9]['state'] == 'native'
    assert count_timeline_coverage(cov) == (9, 9)
    assert cov['next_import_period'] is None


def test_revoquer_un_import_optionnel_ne_cree_pas_un_mois_manquant():
    cov = _couverture_reprise(Bascule(2026, 9), through=10, revoked_periods=['2026-10'])
    assert cov['last_period'] == '2026-09'
    assert cov['timeline'][9]['state'] == 'native'
    assert count_timeline_coverage(cov) == (9, 9)
    assert cov['status'] == 'ok'


def test_matrice_ne_signale_pas_de_retard_sur_une_annee_sans_import_attendu():
    from app.modules.dsn_import.application.coverage import compute_admin_coverage_matrix

    with (
        patch('app.modules.dsn_import.application.coverage.lire_bascule', return_value=Bascule(2026, 9)),
        patch('app.modules.dsn_import.application.coverage._reference_for_matrix_year', return_value=date(2027, 1, 1)),
    ):
        matrix = compute_admin_coverage_matrix(
            [{'id': 'societe-test', 'dsn_sync_mode': 'native'}],
            year=2027, batches=[], revoked_by_company={},
        )
    assert matrix['companies'][0]['status'] == 'not_applicable'
    assert all(m['state'] == 'native' for m in matrix['companies'][0]['timeline'])


def test_les_imports_s_arretent_a_la_bascule_et_octobre_ne_manque_pas():
    cov = _couverture_reprise(Bascule(2026, 9))
    assert cov['expected_last_period'] == '2026-09'
    assert cov['import_cutoff_period'] == '2026-09'
    assert cov['status'] == 'ok'
    assert cov['gaps'] == [] and cov['alerts'] == []
    assert cov['next_import_period'] is None
    assert count_timeline_coverage(cov) == (9, 9)
    assert [m['state'] for m in cov['timeline'][9:]] == ['native'] * 3


def test_la_bascule_ne_fait_pas_croire_que_les_dsn_manquantes_sont_importees():
    cov = _couverture_reprise(Bascule(2026, 9), through=5)
    assert cov['last_period'] == '2026-05'
    assert cov['gaps'] == ['2026-06', '2026-07', '2026-08', '2026-09']
    assert cov['status'] == 'missing'
    assert cov['next_import_period'] == '2026-06'


def test_la_fin_des_imports_depend_de_la_societe_et_non_de_septembre_en_dur():
    cov = _couverture_reprise(Bascule(2026, 8), through=8)
    assert cov['expected_last_period'] == '2026-08'
    assert count_timeline_coverage(cov) == (8, 8)
    assert cov['timeline'][8]['state'] == 'native'


def test_sans_bascule_les_imports_externes_continuent_d_etre_attendus():
    cov = _couverture_reprise(None)
    assert cov['expected_last_period'] == '2026-10'
    assert cov['import_cutoff_period'] is None
    assert cov['timeline'][9]['state'] == 'missing'


def test_une_bascule_future_n_anticipe_pas_des_imports_non_encore_attendus():
    cov = _couverture_reprise(Bascule(2026, 12))
    assert cov['expected_last_period'] == '2026-10'
    assert cov['timeline'][10]['state'] == 'future'


def test_la_bascule_de_l_annee_precedente_ne_cree_pas_d_imports_pour_l_annee_courante():
    cov = _couverture_reprise(Bascule(2025, 12))
    assert cov['expected_last_period'] == '2025-12'
    assert cov['gaps'] == []
    assert all(m['state'] == 'native' for m in cov['timeline'])
    assert count_timeline_coverage(cov) == (0, 0)


def test_expected_last_period_before_grace():
    company = {"paie_occurrence": 25}
    ref = date(2026, 6, 16)
    assert expected_last_period(company, ref) == "2026-05"


def test_compute_coverage_native_not_applicable():
    company = {
        "id": "c1",
        "dsn_sync_mode": "native",
        "siret": "95147478200020",
        "siren": "951474782",
    }
    cov = compute_coverage(company, batches=[])
    assert cov["status"] == "not_applicable"
    assert cov["alerts"] == []


def test_compute_coverage_never_imported():
    company = {
        "id": "c1",
        "dsn_sync_mode": "external",
        "siret": "95147478200020",
        "siren": "951474782",
    }
    cov = compute_coverage(company, batches=[], reference=date(2026, 6, 16))
    assert cov["status"] == "never"
    assert any(a["code"] == "dsn_never_imported" for a in cov["alerts"])


def test_merge_dsn_alerts_rh_copy():
    alerts = merge_dsn_alerts_into_overview(
        [],
        {
            "alerts": [
                {
                    "code": "dsn_month_missing",
                    "severity": "warning",
                    "expected_period": "2026-05",
                }
            ]
        },
    )
    assert "2026-05" in alerts[0]["label"]
    assert alerts[0]["action"] == "contact_admin"


def test_compute_admin_coverage_matrix():
    from app.modules.dsn_import.application.coverage import (
        compute_admin_coverage_matrix,
    )

    companies = [
        {
            "id": "c1",
            "company_name": "Alpha",
            "dsn_sync_mode": "external",
            "siret": "11111111100011",
            "siren": "111111111",
            "group_name": "G1",
        },
        {
            "id": "c2",
            "company_name": "Beta",
            "dsn_sync_mode": "native",
            "siret": "22222222200022",
            "siren": "222222222",
            "group_name": "G1",
        },
    ]
    batches = [
        {
            "id": "b1",
            "status": "committed",
            "siren": "111111111",
            "period_min": "2026-01",
            "period_max": "2026-01",
            "summary": {
                "commit_report": {"target_company_id": "c1"},
                "periods_committed": ["2026-01"],
            },
            "created_at": "2026-02-01T00:00:00Z",
        }
    ]
    matrix = compute_admin_coverage_matrix(companies, year=2026, batches=batches)
    assert matrix["year"] == 2026
    assert len(matrix["companies"]) == 2
    alpha = next(c for c in matrix["companies"] if c["company_id"] == "c1")
    beta = next(c for c in matrix["companies"] if c["company_id"] == "c2")
    assert "2026-01" in alpha["months_covered"]
    assert len(alpha["timeline"]) == 12
    assert beta["status"] == "missing"


def test_compute_coverage_excludes_revoked_periods():
    company = {
        "id": "c1",
        "dsn_sync_mode": "external",
        "siret": "11111111100011",
        "siren": "111111111",
    }
    batches = [
        {
            "id": "b1",
            "status": "committed",
            "siren": "111111111",
            "period_min": "2026-01",
            "period_max": "2026-02",
            "summary": {
                "commit_report": {"target_company_id": "c1"},
                "periods_committed": ["2026-01", "2026-02"],
            },
            "created_at": "2026-03-01T00:00:00Z",
        }
    ]
    cov = compute_coverage(
        company,
        batches=batches,
        reference=date(2026, 6, 16),
        revoked_periods=["2026-02"],
    )
    assert "2026-01" in cov["months_covered"]
    assert "2026-02" not in cov["months_covered"]
    feb = next(m for m in cov["timeline"] if m["period"] == "2026-02")
    assert feb["state"] == "missing"


def test_resolve_next_import_period_first_missing():
    cov = {
        "timeline": [
            {"period": "2026-01", "state": "missing"},
            {"period": "2026-02", "state": "missing"},
            {"period": "2026-06", "state": "future"},
        ],
        "gaps": [],
    }
    assert resolve_next_import_period(cov) == "2026-01"


def test_compute_coverage_includes_next_import_period():
    company = {
        "id": "c1",
        "dsn_sync_mode": "external",
        "siret": "11111111100011",
        "siren": "111111111",
    }
    cov = compute_coverage(company, batches=[], reference=date(2026, 6, 16))
    assert cov["next_import_period"] == "2026-01"


def test_count_timeline_coverage_and_complete():
    coverage = {
        "status": "ok",
        "timeline": [
            {"period": "2026-01", "state": "covered"},
            {"period": "2026-02", "state": "covered"},
            {"period": "2026-03", "state": "missing"},
            {"period": "2026-04", "state": "future"},
        ],
    }
    covered, total = count_timeline_coverage(coverage)
    assert covered == 2
    assert total == 3
    assert is_dsn_coverage_complete(coverage) is True

    coverage["status"] = "missing"
    assert is_dsn_coverage_complete(coverage) is False
