import pytest

pytestmark = pytest.mark.integration

# Scripts manuels interactifs (input(), pas de pytest).
collect_ignore = ["test_login.py", "test_absenteeism.py"]
