"""Le détail d'un bulletin dit quand il a été calculé.

L'onglet « Corriger » lisait les primes sur les lignes du bulletin : une prime
saisie après le calcul n'y était pas, et l'écran affirmait « Aucune prime
saisie pour ce mois » (relevé J.1). Avec la date du dernier calcul, il montre
les saisies enregistrées depuis, pas encore sur le bulletin.
"""

from datetime import datetime, timezone

from app.modules.payslips.schemas.responses import PayslipDetail

DETAIL = {
    "id": "ps-1",
    "employee_id": "e1",
    "company_id": "c1",
    "name": "Bulletin.pdf",
    "month": 9,
    "year": 2026,
    "url": "https://exemple/bulletin.pdf",
    "pdf_storage_path": "c1/e1/bulletin.pdf",
    "payslip_data": {},
    "generated_at": "2026-10-12T16:52:00+00:00",
}


def test_la_date_du_calcul_survit_au_schema():
    rendu = PayslipDetail(**DETAIL).model_dump()
    assert rendu["generated_at"] == datetime(2026, 10, 12, 16, 52, tzinfo=timezone.utc)


def test_sans_date_du_calcul_rien_n_est_invente():
    sans = {k: v for k, v in DETAIL.items() if k != "generated_at"}
    assert PayslipDetail(**sans).model_dump()["generated_at"] is None
