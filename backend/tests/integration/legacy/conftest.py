import pytest

pytestmark = pytest.mark.integration

# Scripts manuels, pas des tests : ils exécutent leur code dès l'import, donc à
# la simple collecte par pytest. Les quatre derniers écrivent : un upsert dans
# `employee_schedules`, deux dépôts de PDF dans le Storage, un PDF dans l'arbre
# du dépôt. Ils ne doivent jamais être chargés.
collect_ignore = [
    "test_login.py",
    "test_absenteeism.py",
    "test_upsert.py",
    "test_upload.py",
    "test_create_employee.py",
    "test_pdf.py",
]
