"""La réponse « salarié seul » ne perd aucune colonne de la table employees.

Fuckar (Colorplast, 12/09/2026) : la fin de contrat de son CDD s'enregistrait
mais ne se relisait jamais — `FullEmployee` ne déclarait pas
`contract_end_date`, et Pydantic ignore les champs inconnus. La fiche, en
lecture comme après enregistrement, affichait un champ vide.
"""

import pytest

from app.modules.employees.schemas.responses import FullEmployee

pytestmark = pytest.mark.unit

# Colonnes de `public.employees` (information_schema, 13/09/2026). Une colonne
# ajoutée en base doit être ajoutée ici ET dans FullEmployee.
COLONNES_EMPLOYEES = (
    "id employee_folder_name first_name last_name nir date_naissance lieu_naissance "
    "nationalite adresse coordonnees_bancaires hire_date contract_type statut job_title "
    "periode_essai is_temps_partiel duree_hebdomadaire salaire_de_base "
    "classification_conventionnelle elements_variables avantages_en_nature specificites_paie "
    "created_at updated_at user_id email username company_id employment_status "
    "current_exit_id account_deactivated_at account_deactivated_reason "
    "is_subject_to_residence_permit residence_permit_expiry_date residence_permit_type "
    "residence_permit_number collective_agreement_id is_poste_sir is_travail_nuit service_id "
    "team_id date_conclusion_contrat date_debut_execution contract_end_date "
    "prior_service_months phone_number sexe nom_usage seniority_reference_date "
    "salary_payment_method matricule is_forfait_jour time_tracking_id"
).split()


def _fuckar(**extra):
    return FullEmployee(
        id="e-fuckar",
        employee_folder_name="FUCKAR_Hugo",
        username="hfuckar",
        first_name="Hugo",
        last_name="FUCKAR",
        contract_type="CDD",
        **extra,
    )


def test_la_fin_de_contrat_est_relue():
    reponse = _fuckar(contract_end_date="2026-09-15").model_dump(mode="json")
    assert reponse["contract_end_date"] == "2026-09-15"


def test_chaque_colonne_de_la_table_a_son_champ():
    manquantes = [c for c in COLONNES_EMPLOYEES if c not in FullEmployee.model_fields]
    assert manquantes == []


def test_les_dates_de_contrat_et_le_matricule_sont_relus():
    reponse = _fuckar(
        date_conclusion_contrat="2026-04-01",
        date_debut_execution="2026-04-07",
        matricule="FUCKAR",
        sexe="M",
    ).model_dump(mode="json")
    assert reponse["date_debut_execution"] == "2026-04-07"
    assert reponse["date_conclusion_contrat"] == "2026-04-01"
    assert reponse["matricule"] == "FUCKAR"
    assert reponse["sexe"] == "M"
