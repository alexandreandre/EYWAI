"""La liste des saisies rend le nom de l'employé, pas seulement son identifiant."""

from app.modules.saisies_avances.schemas.responses import SalarySeizure


def test_employee_name_survit_au_schema_de_reponse():
    ligne = {
        "id": "s-1", "company_id": "c-1", "employee_id": "e-1", "type": "saisie_arret",
        "creditor_name": "SAISIE SGC OYONNAX", "amount": 46.49, "calculation_mode": "fixe",
        "start_date": "2026-07-01", "end_date": "2026-07-31", "status": "active", "priority": 4,
        "created_at": "2026-09-12T07:03:03+00:00", "updated_at": "2026-09-12T07:03:03+00:00", "employee_name": "Marion GAUTHERON",
    }
    assert SalarySeizure(**ligne).model_dump()["employee_name"] == "Marion GAUTHERON"


def test_sans_nom_le_champ_est_vide_et_le_schema_passe():
    ligne = {
        "id": "s-1", "company_id": "c-1", "employee_id": "e-1", "type": "saisie_arret",
        "creditor_name": "X", "calculation_mode": "fixe", "start_date": "2026-07-01",
        "status": "active", "priority": 1, "created_at": "2026-09-12T07:03:03+00:00", "updated_at": "2026-09-12T07:03:03+00:00",
    }
    assert SalarySeizure(**ligne).employee_name is None
