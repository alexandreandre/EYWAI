"""
Centralisation des chemins du moteur de paie (données + templates à l’exécution).

Racine runtime : ``app/runtime/payroll/`` (sous le package ``app``), avec la même
arborescence logique qu’auparavant : ``data/`` (employés, entreprise.json, barèmes)
et ``templates/`` (bulletins). Tous les accès passent par les accesseurs ci-dessous.

Usages typiques :
- payslip_generator, payslip_generator_forfait : ``payroll_engine_root()``,
  ``payroll_engine_employee_folder()``, ``payroll_engine_entreprise_json()``
- payslip_editor : ``payroll_engine_templates()``, ``payroll_engine_employee_bulletins()``
- simulated_payslip_generator : ``payroll_engine_templates()``
- schedules (calendriers / horaires), monthly_inputs : ``payroll_engine_employee_folder()``,
  ``payroll_engine_root()``
- ``app.modules.schedules.infrastructure.providers.FileCalendarProvider`` : idem

Alias : ``PATH_TO_PAYROLL_ENGINE`` = ``PAYROLL_ENGINE_ROOT`` (compat. ``core.config``).
"""

from __future__ import annotations

from pathlib import Path

# backend_api/app/core/paths.py -> parent.parent = backend_api/app
_APP_DIR = Path(__file__).resolve().parent.parent

# Racine runtime paie : data/ + templates/ (plus de dépendance à backend_calculs/).
PAYROLL_ENGINE_ROOT: Path = _APP_DIR / "runtime" / "payroll"

# Alias pour compatibilité (app.core.config, backend_api/core/config).
PATH_TO_PAYROLL_ENGINE: Path = PAYROLL_ENGINE_ROOT

# Racine du module payroll (code métier / engine), distinct du runtime disque.
PAYROLL_MODULE_ROOT: Path = _APP_DIR / "modules" / "payroll"

# backend_api (pour scraping, tests, etc.)
_API_DIR = _APP_DIR.parent

# Racine du dépôt (parent de backend_api/) — monorepo : frontend/, e2e/, etc.
REPO_ROOT: Path = _API_DIR.parent


def payroll_engine_root() -> Path:
    """Racine du runtime paie (contient ``data/`` et ``templates/``)."""
    return PAYROLL_ENGINE_ROOT


def payroll_engine_data() -> Path:
    """Chemin vers ``data/`` (employes, entreprise.json, barèmes)."""
    return PAYROLL_ENGINE_ROOT / "data"


def payroll_engine_templates() -> Path:
    """Chemin vers ``templates/`` (bulletins, styles)."""
    return PAYROLL_ENGINE_ROOT / "templates"


def payroll_engine_employees_dir() -> Path:
    """Chemin vers ``data/employes/``."""
    return payroll_engine_data() / "employes"


def payroll_engine_employee_folder(employee_folder_name: str) -> Path:
    """Chemin vers ``data/employes/<employee_folder_name>/``."""
    return payroll_engine_employees_dir() / employee_folder_name


def payroll_engine_entreprise_json() -> Path:
    """Chemin vers ``data/entreprise.json``."""
    return payroll_engine_data() / "entreprise.json"


def payroll_engine_employee_bulletins(employee_folder_name: str) -> Path:
    """Chemin vers ``data/employes/<name>/bulletins/``."""
    return payroll_engine_employee_folder(employee_folder_name) / "bulletins"


def payroll_engine_baremes() -> Path:
    """Chemin vers ``data/baremes/``. Créé à la demande si besoin."""
    return payroll_engine_data() / "baremes"


# Racine des scripts de scraping (backend_api/scraping/).
SCRAPING_ROOT: Path = _API_DIR / "scraping"

# Répertoire des tests (backend_api/tests/).
TESTS_DIR: Path = _API_DIR / "tests"
